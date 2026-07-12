import type { Metadata } from "next";
import ImageEditor from "../../components/ImageEditor";

export const metadata: Metadata = {
  title: "1280×720 Fotoğraf Kırpma | Yeni Bakış",
  description: "Fotoğraf kadrajını seçin ve 1280×720 WebP olarak indirin.",
};

export default function CropPage() {
  return <ImageEditor tool="crop" />;
}
