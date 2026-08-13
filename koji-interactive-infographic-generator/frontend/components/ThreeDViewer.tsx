// Metro selects ThreeDViewer.web.tsx or ThreeDViewer.native.tsx at runtime.
// This re-export gives TypeScript a platform-neutral component signature.
export { default } from "./ThreeDViewer.native";
