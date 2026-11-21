import { redirect } from "next/navigation";

// 피아노 채보는 악기를 고르는 /transcribe로 합쳐졌다. 예전 링크를 위해 남겨둔다.
export default async function PianoRedirect({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const { media } = await searchParams;
  const params = new URLSearchParams({ instrument: "piano" });
  if (typeof media === "string") params.set("media", media);
  redirect(`/transcribe?${params}`);
}
