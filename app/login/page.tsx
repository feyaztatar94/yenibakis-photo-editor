import type { Metadata } from "next";
import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import LoginForm from "../components/LoginForm";
import { COOKIE_NAME, isValidSession } from "../auth.server";
import { SiteFooter } from "../components/ImageEditor";

export const dynamic = "force-dynamic";
export const metadata: Metadata = { title: "Editör Girişi | Yeni Bakış Görsel Atölyesi" };

export default async function LoginPage() {
  const store = await cookies();
  if (await isValidSession(store.get(COOKIE_NAME)?.value)) redirect("/resizer");
  return (
    <main className="login-page">
      <section className="login-card">
        <span className="login-logo-window"><img src="/yenibakis-logo-transparent.png" alt="Yeni Bakış" /></span>
        <span className="eyebrow">EDİTÖR ARAÇLARI</span>
        <h1>Görsel Atölyesi’ne giriş yapın</h1>
        <p>Fotoğrafları boyutlandırmak veya 1280×720 kırpmak için editör hesabınızla devam edin.</p>
        <LoginForm />
        <small>Görseller yalnızca tarayıcınızda işlenir.</small>
      </section><SiteFooter />
    </main>
  );
}
