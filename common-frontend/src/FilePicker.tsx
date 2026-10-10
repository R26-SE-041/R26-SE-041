import React from 'react';
import { Text } from 'react-native';
export type Upload = { name: string; file: Blob };
export default function FilePicker(_: { accept: string; onPick: (file: Upload) => void; disabled?: boolean }) { return <Text>File uploads are available in the web app. Native file picking will be added during mobile integration.</Text>; }
