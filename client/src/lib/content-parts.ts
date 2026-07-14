import type { ThreadAssistantMessagePart } from "@assistant-ui/react";

interface ContentPartOptions {
  createObjectUrl?: (blob: Blob) => string;
  fetcher?: typeof fetch;
  origin?: string;
}

const IMAGE_CACHE_TTL_MS = 5 * 60 * 1000;

interface CachedImage {
  promise: Promise<string>;
  ts: number;
}

const imageUrlCache = new Map<string, CachedImage>();
const PUBLIC_IMAGE_URL_PATTERN = /^(blob:|https:)/;

function evictStaleImages(now: number): void {
  for (const [key, value] of imageUrlCache) {
    if (now - value.ts > IMAGE_CACHE_TTL_MS) {
      imageUrlCache.delete(key);
    }
  }
}

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

  const now = Date.now();
  evictStaleImages(now);
  const cached = imageUrlCache.get(absoluteImageUrl);
  if (cached) {
    return cached.promise;
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

  imageUrlCache.set(absoluteImageUrl, { promise: pendingUrl, ts: now });
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

  const resolvedParts = await Promise.all(
    parts.map(async (part): Promise<ThreadAssistantMessagePart | null> => {
      if (part.type === "source") {
        return null;
      }

      if (part.type === "image") {
        return {
          ...part,
          image: await toAssistantImageUrl(part.image, resolvedOptions),
        };
      }

      return part;
    })
  );
  const displayParts = resolvedParts.filter(
    (part): part is ThreadAssistantMessagePart => part !== null
  );

  return [
    ...displayParts.filter((part) => part.type === "image"),
    ...displayParts.filter((part) => part.type !== "image"),
  ];
}
