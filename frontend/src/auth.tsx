/* All Clerk-touching code lives here. Without VITE_CLERK_PUBLISHABLE_KEY the
   app renders open (matches the backend's empty-CLERK_SECRET_KEY dev mode). */
import { ClerkProvider, SignIn, SignedIn, SignedOut, useAuth, useUser } from "@clerk/clerk-react";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { setAuthTokenGetter } from "./api";
import { MivaMark } from "./ds";

export const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

interface AuthInfo {
  email: string | null;
  signOut: (() => void) | null;
}
const AuthCtx = createContext<AuthInfo>({ email: null, signOut: null });
export const useAuthInfo = () => useContext(AuthCtx);

function TokenBridge({ children }: { children: ReactNode }) {
  const { getToken, signOut } = useAuth();
  const { user } = useUser();
  useEffect(() => {
    setAuthTokenGetter(() => getToken());
    return () => setAuthTokenGetter(null);
  }, [getToken]);
  return (
    <AuthCtx.Provider
      value={{ email: user?.primaryEmailAddress?.emailAddress ?? null, signOut: () => { void signOut(); } }}
    >
      {children}
    </AuthCtx.Provider>
  );
}

export function AuthShell({ children }: { children: ReactNode }) {
  if (!PUBLISHABLE_KEY) return <>{children}</>;
  return (
    <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
      <SignedIn>
        <TokenBridge>{children}</TokenBridge>
      </SignedIn>
      <SignedOut>
        <div
          style={{
            height: "100%", display: "flex", flexDirection: "column", alignItems: "center",
            justifyContent: "center", gap: "var(--s-6)", background: "var(--nav-bg)",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "var(--s-3)" }}>
            <MivaMark height={34} />
            <span style={{ fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "var(--text-h3)", color: "#fff" }}>
              VisageIQ
            </span>
          </div>
          <SignIn />
        </div>
      </SignedOut>
    </ClerkProvider>
  );
}
