import React, { createContext, useContext, useEffect, useState } from "react";
import { Platform } from "react-native";
import { type AccountState, clearCrossTabSession, initializeAuth, subscribeAuth } from "@/lib/auth";

const AuthContext = createContext<AccountState>({ enabled: true, loading: true, user: null, error: "" });
export const useAccount = () => useContext(AuthContext);

export default function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AccountState>({ enabled: true, loading: true, user: null, error: "" });
  useEffect(() => {
    const unsubscribe = subscribeAuth(setState);
    void initializeAuth();
    if (Platform.OS === "web") window.addEventListener("storage", clearCrossTabSession);
    return () => {
      unsubscribe();
      if (Platform.OS === "web") window.removeEventListener("storage", clearCrossTabSession);
    };
  }, []);
  return <AuthContext.Provider value={state}>{children}</AuthContext.Provider>;
}
