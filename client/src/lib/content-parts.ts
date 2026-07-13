import type { ThreadAssistantMessagePart } from "@assistant-ui/react";

interface ContentPartOptions {
  createObjectUrl?: (blob: Blob) => string;
  fetcher?: typeof fetch;
  origin?: string;
}

const imageUrlCache = new Map<string, Promise<string>>();
const PUBLIC_IMAGE_URL_PATTERN = /^(blob:|https:)/;

function toAbsoluteImageUrl(image: string, origin?: string): string {
  if (!(image.startsWith("/") && origin)) {
    return image;
  }

  return new URL(image, origin).toString();
}

function toAssistantImageUrl(
  image: string,
  { createObjectUrl, fetcher, origin }: ContentPartOptions
): Promise<string> {
  const absoluteImageUrl = toAbsoluteImageUrl(image, origin);
  if (PUBLIC_IMAGE_URL_PATTERN.test(absoluteImageUrl)) {
    return Promise.resolve(absoluteImageUrl);
  }

  const cached = imageUrlCache.get(absoluteImageUrl);
  if (cached) {
    return cached;
  }

  if (!(fetcher && createObjectUrl)) {
    return Promise.resolve(absoluteImageUrl);
  }

  const pendingUrl = fetcher(absoluteImageUrl)
    .then((response) => {
      if (!response.ok) {
        throw new Error(`Unable to load retrieved image (${response.status}).`);
      }
      return response.blob();
    })
    .then(createObjectUrl);

  imageUrlCache.set(absoluteImageUrl, pendingUrl);
  pendingUrl.catch(() => imageUrlCache.delete(absoluteImageUrl));
  return pendingUrl;
}

export async function toDisplayContentParts(
  parts: readonly ThreadAssistantMessagePart[],
  options: ContentPartOptions = {}
): Promise<ThreadAssistantMessagePart[]> {
  const resolvedOptions: ContentPartOptions = {
    createObjectUrl:
      options.createObjectUrl ??
      (typeof URL === "undefined" ? undefined : URL.createObjectURL),
    fetcher:
      options.fetcher ?? (typeof fetch === "undefined" ? undefined : fetch),
    origin:
      options.origin ??
      (typeof window === "undefined" ? undefined : window.location.origin),
  };

  const displayParts = await Promise.all(
    parts.flatMap((part) => {
      if (part.type === "source") {
        return [];
      }

      if (part.type === "image") {
        return toAssistantImageUrl(part.image, resolvedOptions).then(
          (image) => ({
            ...part,
            image,
          })
        );
      }

      return [part];
    })
  );

  return [
    ...displayParts.filter((part) => part.type === "image"),
    ...displayParts.filter((part) => part.type !== "image"),
  ];
}
