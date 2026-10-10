import React from 'react';
import { Text } from 'react-native';
import type { Upload } from './FilePicker';
export default function Recorder(_: { onRecorded: (file: Upload) => void; disabled?: boolean }) { return <Text>Voice recording is currently available on web.</Text>; }
