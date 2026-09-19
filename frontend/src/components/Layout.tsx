import { Link, Outlet } from "react-router";

export function Layout() {
  return (
    <>
      <nav>
        <Link to="/">Listings</Link> | <Link to="/new">New Listing</Link>
      </nav>
      <main>
        <Outlet />
      </main>
    </>
  );
}
