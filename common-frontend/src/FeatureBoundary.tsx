import React from 'react';
import { Button, Card, Notice, styles } from './ui';
import { Text } from 'react-native';
export default class FeatureBoundary extends React.Component<{ children: React.ReactNode; name: string }, { error: boolean; retry: number }> {
  state = { error: false, retry: 0 };
  static getDerivedStateFromError() { return { error: true }; }
  render() {
    if (this.state.error) return <Card><Text style={styles.heading}>{this.props.name}</Text><Notice error text="This workspace encountered a display error. Your other learning tools remain available." /><Button label="Reopen workspace" onPress={() => this.setState({ error: false, retry: this.state.retry + 1 })} /></Card>;
    return <React.Fragment key={this.state.retry}>{this.props.children}</React.Fragment>;
  }
}
