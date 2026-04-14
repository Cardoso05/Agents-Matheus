import { Dropzone } from "@/components/upload/dropzone";

export default function UploadPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold">Upload de Extratos</h1>
        <p className="text-muted-foreground">
          Faça upload dos seus extratos bancários em PDF, CSV ou OFX
        </p>
      </div>
      <Dropzone />
    </div>
  );
}
