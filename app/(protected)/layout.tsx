import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { COOKIE_NAME, isValidSession } from "../auth.server";

export const dynamic = "force-dynamic";

export default async function ProtectedLayout({ children }: { children: React.ReactNode }) {
  const store = await cookies();
  if (!(await isValidSession(store.get(COOKIE_NAME)?.value))) redirect("/login");
  return children;
}
