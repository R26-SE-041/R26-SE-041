import React from 'react';
import { Linking, Pressable, ScrollView, Text, View } from 'react-native';
import { components } from './components';

// Metro selects Launcher.web.tsx for the dashboard website.
export default function Launcher() {
  return <ScrollView contentContainerStyle={{ padding: 24, gap: 20, backgroundColor: '#f7f8f2' }}>
    <Text accessibilityRole="header" style={{ fontSize: 34, color: '#183e34' }}>LearnX</Text>
    <Text>One space. Four ways to learn biology.</Text>
    {components.map(component => <Pressable key={component.id} accessibilityRole="link" onPress={() => Linking.openURL(component.url)} style={{ padding: 24, borderRadius: 16, backgroundColor: component.background, gap: 12 }}>
      <Text style={{ fontSize: 24, color: '#183e34' }}>{component.name} ↗</Text>
      <Text>{component.description}</Text>
    </Pressable>)}
    <View><Text>Each component uses its own account. Sign in within the app you open.</Text></View>
  </ScrollView>;
}
