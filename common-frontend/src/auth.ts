import 'react-native-url-polyfill/auto';
import AsyncStorage from '@react-native-async-storage/async-storage';
import { createClient } from '@supabase/supabase-js';
import { Platform } from 'react-native';
const url = process.env.EXPO_PUBLIC_SUPABASE_URL;
const key = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY;
export const auth = url && key ? createClient(url, key, { auth: {
  storage: AsyncStorage, storageKey: `biolearnx-common-auth:${new URL(url).host}`, persistSession: true,
  autoRefreshToken: true, detectSessionInUrl: Platform.OS === 'web',
} }) : null;
