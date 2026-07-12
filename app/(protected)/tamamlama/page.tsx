import type { Metadata } from "next";
import ImageEditor from "../../components/ImageEditor";

export const metadata: Metadata = { title: "Fotoğraf Tamamlama | Yeni Bakış", description: "Fotoğrafı beyaz 1280×720 zemine yerleştirin." };
export default function CompletionPage() { return <ImageEditor tool="complete" />; }
