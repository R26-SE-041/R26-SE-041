import { useEffect, useState } from "react";
import { Image } from "react-native";

/** Measure the source, never the rendered (possibly letterboxed) image. */
export default function useImageAspectRatio(uri: string): number {
  const [size, setSize] = useState({ uri: "", ratio: 1 });
  useEffect(() => {
    let active = true;
    Image.getSize(uri, (width, height) => {
      if (active && width > 0 && height > 0) setSize({ uri, ratio: width / height });
    }, () => {});
    return () => { active = false; };
  }, [uri]);
  return size.uri === uri ? size.ratio : 1;
}
