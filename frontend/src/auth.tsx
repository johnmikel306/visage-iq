/* All Clerk-touching code lives here. Without VITE_CLERK_PUBLISHABLE_KEY the
   app renders open (matches the backend's empty-CLERK_SECRET_KEY dev mode). */
import {
  ClerkLoading,
  ClerkProvider,
  OrganizationSwitcher,
  SignIn,
  SignedIn,
  SignedOut,
  UserButton,
  useAuth,
  useClerk,
  useUser,
} from "@clerk/clerk-react";
import { dark } from "@clerk/themes";
import { useEffect, useRef, type ReactNode } from "react";
import { setAuthTokenGetter } from "./api";
import { Icon, VqLoader, VqLockup, VqMark } from "./ds";

const HANDOFF_MSGS = [
  "Loading the enrolment index…",
  "Checking Drive sync state…",
  "Warming the vector cache…",
  "Reading your review thresholds…",
  "Preparing the workspace…",
];

export const PUBLISHABLE_KEY = import.meta.env.VITE_CLERK_PUBLISHABLE_KEY as string | undefined;

function TokenBridge({ children }: { children: ReactNode }) {
  const { getToken } = useAuth();
  // Register DURING render, not in an effect: child effects run before parent
  // effects, so App's mount-time fetches would otherwise fire tokenless. The
  // ref keeps the getter current without re-registering machinery.
  const getTokenRef = useRef(getToken);
  getTokenRef.current = getToken;
  setAuthTokenGetter(() => getTokenRef.current());
  useEffect(() => () => setAuthTokenGetter(null), []);
  return <>{children}</>;
}

/* B2B: Miva Open University org, manual invitations — invited users accept via
   this switcher or the email link. Renders nothing in no-auth dev mode (outside
   ClerkProvider the component would throw). */
export function OrgControl() {
  if (!PUBLISHABLE_KEY) return null;
  return (
    <OrganizationSwitcher
      hidePersonal
      appearance={{
        elements: {
          organizationSwitcherTrigger: { color: "rgba(255,255,255,.72)", padding: "4px 6px" },
        },
      }}
    />
  );
}

/* Sidebar-footer user chip: Clerk's UserButton (avatar → menu → full profile
   modal) plus the display name. Sign-out lives in the dropdown. Org admins get
   an extra "Manage organization" action — the RBAC hook until proper roles land. */
export function UserControl({ isDark }: { isDark: boolean }) {
  if (!PUBLISHABLE_KEY) return null;
  return <UserChip isDark={isDark} />;
}

function UserChip({ isDark }: { isDark: boolean }) {
  const { user } = useUser();
  const { orgRole } = useAuth();
  const clerk = useClerk();
  // v5 parses variable colors, so resolve the palette token to a real value.
  const focus = getComputedStyle(document.documentElement).getPropertyValue("--focus").trim();
  const appearance = {
    baseTheme: isDark ? dark : undefined,
    variables: { colorPrimary: focus, fontFamily: "var(--font-body)" },
  };
  const email = user?.primaryEmailAddress?.emailAddress ?? "";
  return (
    <div className="row" style={{ gap: "var(--s-2)", flexWrap: "nowrap" }}>
      <UserButton appearance={appearance} userProfileProps={{ appearance }}>
        {orgRole === "org:admin" && (
          <UserButton.MenuItems>
            <UserButton.Action
              label="Manage organization"
              labelIcon={<Icon name="shield" size={14} />}
              onClick={() => clerk.openOrganizationProfile({ appearance })}
            />
          </UserButton.MenuItems>
        )}
      </UserButton>
      <span className="side-meta hide-collapsed" title={email}>
        {user?.fullName || email}
      </span>
    </div>
  );
}

export function AuthShell({ children }: { children: ReactNode }) {
  if (!PUBLISHABLE_KEY) return <>{children}</>;
  return (
    <ClerkProvider publishableKey={PUBLISHABLE_KEY} afterSignOutUrl="/">
      <ClerkLoading>
        {/* Handoff loader (Auth screens, screen 9) — bridges page load and session resolution. */}
        <div style={{ height: "100%", display: "grid", placeItems: "center", background: "var(--surface-2)" }}>
          <VqLoader lockup messages={HANDOFF_MSGS} />
        </div>
      </ClerkLoading>
      <SignedIn>
        <TokenBridge>{children}</TokenBridge>
      </SignedIn>
      <SignedOut>
        {/* Sign-in (Auth screens, screen 1): dark aside with the lockup and
            access note; form pane carries Clerk's card. Google is the only
            enabled method, so the card renders as the SSO-first route. */}
        <div className="auth-screen">
          <aside className="auth-aside">
            <VqLockup mark={26} type={21} onDark />
            <div className="pitch">Face match operations for the registry.</div>
            <div className="foot">
              Access is limited to authorised registry and examination staff. Every search is logged.
            </div>
            <div className="watermark" aria-hidden="true">
              <VqMark size={250} onDark />
            </div>
          </aside>
          <div className="auth-pane">
            <div style={{ textAlign: "center" }}>
              <h1>Sign in to VisageIQ</h1>
              <p className="lede">Use your Miva staff Google account.</p>
            </div>
            {/* hash routing keeps the OAuth callback inside this single-page app
                (no router), and forceRedirectUrl lands the user back here instead
                of Clerk's hosted accounts.dev portal / default-redirect page. */}
            <SignIn routing="hash" forceRedirectUrl="/" />
          </div>
        </div>
      </SignedOut>
    </ClerkProvider>
  );
}
