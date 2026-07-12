"use client";

import { FormEvent, useState } from "react";

export default function LoginForm() {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch("/api/login", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({ username: form.get("username"), password: form.get("password") }),
      });
      const result = (await response.json()) as { message?: string };
      if (!response.ok) return setError(result.message ?? "Giriş yapılamadı.");
      window.location.assign("/");
    } catch {
      setError("Bağlantı kurulamadı. Lütfen tekrar deneyin.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form className="login-form" onSubmit={submit}>
      <label><span>Kullanıcı adı</span><input name="username" autoComplete="username" required autoFocus /></label>
      <label><span>Şifre</span><input name="password" type="password" autoComplete="current-password" required /></label>
      {error && <p className="login-error" role="alert">{error}</p>}
      <button className="primary-button" disabled={busy}>{busy ? "Giriş yapılıyor…" : "Giriş yap"}</button>
    </form>
  );
}
