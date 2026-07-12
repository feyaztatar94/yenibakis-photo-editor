import type { Metadata } from "next";
import CollageEditor from "../../components/CollageEditor";

export const metadata: Metadata = { title: "Fotoğraf Kolajı | Yeni Bakış", description: "İki fotoğrafı 1280×720 kolajda birleştirin." };
export default function CollagePage() { return <CollageEditor />; }
