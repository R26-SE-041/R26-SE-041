import React from 'react';
import { Text } from 'react-native';
import type { AnatomyAnnotation } from '../App';
export default function ImageDownloadControls(_: { annotations: AnatomyAnnotation[]; imageBase64: string; organ?: string }) {
  return <Text>Image and SVG downloads are available on web.</Text>;
}
