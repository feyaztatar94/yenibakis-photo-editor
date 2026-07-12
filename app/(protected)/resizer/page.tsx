import type { Metadata } from "next";
import ImageEditor from "../../components/ImageEditor";

export const metadata: Metadata = {
  title: "Toplu Fotoğraf Boyutlandırma | Yeni Bakış",
  description: "Fotoğrafları ortak genişlikle toplu olarak WebP formatına dönüştürün.",
};

export default function ResizerPage() {
  return <ImageEditor tool="resize" />;
}
