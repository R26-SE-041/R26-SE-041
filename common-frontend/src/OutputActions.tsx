import React from 'react';
import { Text } from 'react-native';
export default function OutputActions(_: { text?: string; name?: string; image?: string; mime?: string }) { return <Text selectable>Use the web workspace to copy or download your results.</Text>; }
export function downloadBlob(_: Blob, _filename: string) { throw new Error('Downloads are currently available on web.'); }
