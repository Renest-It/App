import { Link, Outlet } from "react-router";
import { useAuth } from "../auth/useAuth";
import { useLogout } from "../auth/useLogout";

export function Layout() {
  // TEMPORARY (testing only) — remove before the E1.3 PR. The real log-out button lives on
  // the Account tab in E1.3.5.
  const { user } = useAuth();
  const logout = useLogout();

  return (
    <>
      <nav>
        <Link to="/">Listings</Link> | <Link to="/new">New Listing</Link>
        {user && (
          <>
            {" | "}
            {user.email}{" "}
            <button onClick={logout}>Log out (temporary)</button>
          </>
        )}
      </nav>
      <main>
        <Outlet />
      </main>
    </>
  );
}
