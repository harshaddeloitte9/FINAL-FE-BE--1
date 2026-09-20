import React from "react";

type AuthUser = {
  name: string;
  username: string;
  role?: string | null;
};

type AuthState = {
  user: AuthUser | null;
  isHydrated: boolean;
  login: (username: string, password: string) => void;
  logout: () => void;
};

const AuthContext = React.createContext<AuthState | null>(null);

// Turns a raw username like "jane.doe" or "jane_doe" into a display name
// like "Jane Doe". Purely cosmetic — there is no real identity behind it.
function toDisplayName(username: string): string {
  const trimmed = username.trim();
  if (!trimmed) return "User";
  return trimmed
    .split(/[\s._-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = React.useState<AuthUser | null>(null);
  const [isHydrated, setIsHydrated] = React.useState(false);

  // Demo/dummy authentication only — the "signed in" state intentionally
  // lives ONLY in memory for the current app session (no localStorage/
  // sessionStorage). Opening or reloading the app must always show the
  // login page again; navigating between routes within the same session
  // (no full page reload) keeps this in-memory state intact.
  React.useEffect(() => {
    setIsHydrated(true);
  }, []);

  const DEMO_ROLES = [
    "Risk Validator",
    "Model Risk Analyst",
    "Credit Risk Manager",
    "Model Governance Analyst",
  ];

  const login = React.useCallback((username: string, password: string) => {
    const uname = username.trim();
    // Accept any non-empty username and password for demo; do not
    // validate against hardcoded credentials.
    if (!uname || !password) return;

    // Pick a random demo role for this session.
    const assignedRole = DEMO_ROLES[Math.floor(Math.random() * DEMO_ROLES.length)];

    const nextUser: AuthUser = { name: toDisplayName(uname), username: uname, role: assignedRole };
    setUser(nextUser);
  }, []);

  const logout = React.useCallback(() => {
    setUser(null);
  }, []);

  const value = React.useMemo(
    () => ({ user, isHydrated, login, logout }),
    [user, isHydrated, login, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = React.useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
