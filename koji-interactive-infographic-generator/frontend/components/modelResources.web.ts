import { useEffect, useMemo, useState } from "react";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { clone } from "three/examples/jsm/utils/SkeletonUtils.js";
import { cachedAsset } from "../assetCache";
import { studioOwner } from "../studioClient";

export interface ModelSource { glbBase64?: string; modelUrl?: string; modelKey?: string }
interface Resource { promise: Promise<THREE.Group>; scene?: THREE.Group; users: number; touched: number; bytes: number }
const models = new Map<string, Resource>();
const MAX_PARSED_BYTES = 120 * 1024 * 1024;

function inlineKey(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index++) hash = Math.imul(hash ^ value.charCodeAt(index), 16777619);
  return `inline:${value.length}:${hash >>> 0}`;
}
function trim() {
  let total = [...models.values()].reduce((sum, entry) => sum + entry.bytes, 0);
  for (const [key, entry] of [...models].sort((a,b) => a[1].touched - b[1].touched)) {
    if (models.size <= 12 && total <= MAX_PARSED_BYTES) break;
    if (entry.users || !entry.scene) continue;
    entry.scene.traverse(object => {
      const mesh = object as THREE.Mesh;
      mesh.geometry?.dispose();
      for (const material of mesh.material ? Array.isArray(mesh.material) ? mesh.material : [mesh.material] : []) {
        for (const value of Object.values(material)) if (value instanceof THREE.Texture) value.dispose();
        material.dispose();
      }
    });
    models.delete(key); total -= entry.bytes;
  }
}

export function useModel(source: ModelSource, enabled = true) {
  const owner = studioOwner();
  const key = useMemo(() => `${owner}:${source.modelKey || (source.glbBase64 ? inlineKey(source.glbBase64) : source.modelUrl || "empty")}`, [owner, source.modelKey, source.glbBase64, source.modelUrl]);
  const [scene, setScene] = useState<THREE.Group | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    if (!enabled) { setScene(null); return; }
    let live = true;
    setError(null); setScene(null);
    let entry = models.get(key);
    if (!entry) {
      const resource: Resource = { users: 0, touched: Date.now(), bytes: 0, promise: Promise.resolve(null as unknown as THREE.Group) };
      resource.promise = (async () => {
        let bytes: ArrayBuffer;
        if (source.glbBase64) {
          const binary = atob(source.glbBase64);
          bytes = Uint8Array.from(binary, character => character.charCodeAt(0)).buffer;
        } else if (source.modelUrl) bytes = await cachedAsset(owner, source.modelKey || source.modelUrl, source.modelUrl);
        else throw new Error("The saved model is not available.");
        resource.bytes = bytes.byteLength;
        const gltf = await new GLTFLoader().parseAsync(bytes, "");
        resource.scene = gltf.scene;
        return gltf.scene;
      })();
      entry = resource; models.set(key, entry);
    }
    const retained = entry;
    retained.users++; retained.touched = Date.now();
    void retained.promise.then(original => {
      if (!live) return;
      const copy = clone(original) as THREE.Group;
      const bounds = new THREE.Box3().setFromObject(copy, true);
      if (bounds.isEmpty()) throw new Error("This model contains no visible geometry.");
      const center = bounds.getCenter(new THREE.Vector3());
      const size = bounds.getSize(new THREE.Vector3());
      const scale = 2 / Math.max(size.x, size.y, size.z, .001);
      copy.scale.multiplyScalar(scale); copy.position.sub(center.multiplyScalar(scale));
      setScene(copy);
    }).catch(failure => {
      if (models.get(key) === retained) models.delete(key);
      if (live) setError(failure instanceof Error ? failure.message : "Unable to display this model.");
    });
    return () => { live = false; retained.users--; retained.touched = Date.now(); trim(); };
  }, [key, attempt, enabled]);
  return { scene, error, retry: () => setAttempt(value => value + 1) };
}
