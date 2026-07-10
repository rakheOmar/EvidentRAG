"use client";

import type {
  ImageMessagePart,
  ImageMessagePartComponent,
} from "@assistant-ui/react";
import { cva, type VariantProps } from "class-variance-authority";
import {
  CopyIcon,
  DownloadIcon,
  ImageIcon,
  ImageOffIcon,
  Loader2Icon,
  RefreshCwIcon,
  ShieldAlertIcon,
} from "lucide-react";
import {
  memo,
  type PropsWithChildren,
  useEffect,
  useRef,
  useState,
} from "react";
import { createPortal } from "react-dom";
import { cn } from "@/lib/utils";

const extensionForMimeType = (mimeType?: string): string => {
  switch (mimeType) {
    case "image/png":
      return "png";
    case "image/jpeg":
    case "image/jpg":
      return "jpg";
    case "image/webp":
      return "webp";
    case "image/gif":
      return "gif";
    case "image/svg+xml":
      return "svg";
    default:
      return "png";
  }
};

const dataUriToBlob = (dataUri: string): Blob => {
  const [meta, data] = dataUri.split(",");
  const mime = meta?.match(/data:([^;]+)/)?.[1] ?? "application/octet-stream";
  if (!/;base64/i.test(meta ?? "")) {
    return new Blob([decodeURIComponent(data ?? "")], { type: mime });
  }
  const bytes = atob(data ?? "");
  const arr = new Uint8Array(bytes.length);
  for (let i = 0; i < bytes.length; i++) {
    arr[i] = bytes.charCodeAt(i);
  }
  return new Blob([arr], { type: mime });
};

const mimeFromImage = (image: string): string | undefined =>
  image.match(/^data:([^;,]+)/)?.[1];

const downloadImagePart = (
  part: Pick<ImageMessagePart, "image" | "filename">,
): void => {
  if (typeof document === "undefined") {
    return;
  }
  const ext = extensionForMimeType(mimeFromImage(part.image));
  const filename = part.filename ?? `image.${ext}`;
  const isDataUri = part.image.startsWith("data:");
  const objectUrl = isDataUri
    ? URL.createObjectURL(dataUriToBlob(part.image))
    : null;
  const href = objectUrl ?? part.image;
  const a = document.createElement("a");
  a.href = href;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  if (objectUrl) {
    URL.revokeObjectURL(objectUrl);
  }
};

const copyImagePart = async (
  part: Pick<ImageMessagePart, "image">,
): Promise<void> => {
  if (
    typeof navigator === "undefined" ||
    !navigator.clipboard ||
    typeof ClipboardItem === "undefined"
  ) {
    throw new Error("Clipboard API is not available in this environment.");
  }
  const blob = part.image.startsWith("data:")
    ? dataUriToBlob(part.image)
    : await fetch(part.image).then((r) => r.blob());
  const mime = mimeFromImage(part.image) ?? blob.type ?? "image/png";
  await navigator.clipboard.write([new ClipboardItem({ [mime]: blob })]);
};

const imageVariants = cva(
  "aui-image-root relative overflow-hidden rounded-lg",
  {
    variants: {
      variant: {
        outline: "border border-border",
        ghost: "",
        muted: "bg-muted/50",
      },
      size: {
        sm: "max-w-64",
        default: "max-w-96",
        lg: "max-w-[512px]",
        full: "w-full",
      },
    },
    defaultVariants: {
      variant: "outline",
      size: "default",
    },
  },
);

export type ImageRootProps = React.ComponentProps<"div"> &
  VariantProps<typeof imageVariants>;

function ImageRoot({
  className,
  variant,
  size,
  children,
  ...props
}: ImageRootProps) {
  return (
    <div
      className={cn(imageVariants({ variant, size, className }))}
      data-size={size}
      data-slot="image-root"
      data-variant={variant}
      {...props}
    >
      {children}
    </div>
  );
}

type ImagePreviewProps = Omit<React.ComponentProps<"img">, "children"> & {
  containerClassName?: string;
};

function ImagePreview({
  className,
  containerClassName,
  onLoad,
  onError,
  alt = "Image content",
  src,
  ...props
}: ImagePreviewProps) {
  const imgRef = useRef<HTMLImageElement>(null);
  const [loadedSrc, setLoadedSrc] = useState<string | undefined>(undefined);
  const [errorSrc, setErrorSrc] = useState<string | undefined>(undefined);

  const loaded = loadedSrc === src;
  const error = errorSrc === src;

  useEffect(() => {
    if (
      typeof src === "string" &&
      imgRef.current?.complete &&
      imgRef.current.naturalWidth > 0
    ) {
      setLoadedSrc(src);
    }
  }, [src]);

  return (
    <div
      className={cn("relative min-h-32", containerClassName)}
      data-slot="image-preview"
    >
      {!(loaded || error) && (
        <div
          className="absolute inset-0 flex items-center justify-center bg-muted/50"
          data-slot="image-preview-loading"
        >
          <ImageIcon className="size-8 animate-pulse text-muted-foreground" />
        </div>
      )}
      {error ? (
        <div
          className="flex min-h-32 items-center justify-center bg-muted/50 p-4"
          data-slot="image-preview-error"
        >
          <ImageOffIcon className="size-8 text-muted-foreground" />
        </div>
      ) : (
        <img
          alt={alt}
          className={cn(
            "block h-auto w-full object-contain",
            !loaded && "invisible",
            className,
          )}
          onError={(e) => {
            if (typeof src === "string") {
              setErrorSrc(src);
            }
            onError?.(e);
          }}
          onLoad={(e) => {
            if (typeof src === "string") {
              setLoadedSrc(src);
            }
            onLoad?.(e);
          }}
          ref={imgRef}
          src={src}
          {...props}
        />
      )}
    </div>
  );
}

function ImageFilename({
  className,
  children,
  ...props
}: React.ComponentProps<"span">) {
  if (!children) {
    return null;
  }

  return (
    <span
      className={cn(
        "block truncate px-2 py-1.5 text-muted-foreground text-xs",
        className,
      )}
      data-slot="image-filename"
      {...props}
    >
      {children}
    </span>
  );
}

type ImageZoomProps = PropsWithChildren<{
  src: string;
  alt?: string;
}>;

function ImageZoom({ src, alt = "Image preview", children }: ImageZoomProps) {
  const [isMounted, setIsMounted] = useState(false);
  const [isOpen, setIsOpen] = useState(false);

  useEffect(() => {
    setIsMounted(true);
  }, []);

  const handleOpen = () => setIsOpen(true);
  const handleClose = () => setIsOpen(false);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setIsOpen(false);
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen) {
      return;
    }
    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.body.style.overflow = originalOverflow;
    };
  }, [isOpen]);

  return (
    <>
      <div
        aria-label="Click to zoom image"
        className="aui-image-zoom-trigger cursor-zoom-in"
        onClick={handleOpen}
        onKeyDown={(e) => e.key === "Enter" && handleOpen()}
        role="button"
        tabIndex={0}
      >
        {children}
      </div>
      {isMounted &&
        isOpen &&
        createPortal(
          <div
            aria-label="Close zoomed image"
            className="aui-image-zoom-overlay fade-in fixed inset-0 z-50 flex animate-in items-center justify-center bg-black/80 duration-200"
            data-slot="image-zoom-overlay"
            onClick={handleClose}
            onKeyDown={(e) => e.key === "Enter" && handleClose()}
            role="button"
            tabIndex={0}
          >
            <img
              alt={alt}
              className="aui-image-zoom-content fade-in zoom-in-95 max-h-[90vh] max-w-[90vw] animate-in cursor-zoom-out object-contain duration-200"
              data-slot="image-zoom-content"
              onClick={(e) => {
                e.stopPropagation();
                handleClose();
              }}
              src={src}
            />
          </div>,
          document.body,
        )}
    </>
  );
}

function ImageGenerating({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "flex min-h-32 items-center justify-center bg-muted/50 p-4",
        className,
      )}
      data-slot="image-generating"
    >
      <Loader2Icon className="size-8 animate-spin text-muted-foreground" />
      <span className="sr-only">Generating image…</span>
    </div>
  );
}

function ImageContentFilterError({
  className,
  reason,
}: {
  className?: string;
  reason?: string;
}) {
  return (
    <div
      className={cn(
        "flex min-h-32 flex-col items-center justify-center gap-2 bg-muted/50 p-4 text-center",
        className,
      )}
      data-slot="image-content-filter-error"
    >
      <ShieldAlertIcon className="size-8 text-muted-foreground" />
      <p className="font-medium text-sm">Image could not be generated</p>
      {reason && <p className="text-muted-foreground text-xs">{reason}</p>}
    </div>
  );
}

export type ImageActionsProps = {
  part: ImageMessagePart;
  /**
   * Wire to your own generation call to show a regenerate button. The button
   * renders only when this is set and the part carries a `prompt`.
   */
  onRegenerate?: () => void | Promise<void>;
  className?: string;
};

function RegenerateButton({
  onRegenerate,
}: {
  onRegenerate: () => void | Promise<void>;
}) {
  const [isRegenerating, setIsRegenerating] = useState(false);
  return (
    <button
      aria-label="Regenerate image"
      className="inline-flex size-7 items-center justify-center rounded hover:bg-muted disabled:opacity-50"
      data-slot="image-regenerate"
      disabled={isRegenerating}
      onClick={async () => {
        setIsRegenerating(true);
        try {
          await onRegenerate();
        } finally {
          setIsRegenerating(false);
        }
      }}
      type="button"
    >
      <RefreshCwIcon
        className={cn("size-4", isRegenerating && "animate-spin")}
      />
    </button>
  );
}

function ImageActions({ part, onRegenerate, className }: ImageActionsProps) {
  return (
    <div
      className={cn("flex items-center gap-1 p-1", className)}
      data-slot="image-actions"
    >
      <button
        aria-label="Download image"
        className="inline-flex size-7 items-center justify-center rounded hover:bg-muted"
        data-slot="image-download"
        onClick={() => downloadImagePart(part)}
        type="button"
      >
        <DownloadIcon className="size-4" />
      </button>
      <button
        aria-label="Copy image"
        className="inline-flex size-7 items-center justify-center rounded hover:bg-muted"
        data-slot="image-copy"
        onClick={() => {
          copyImagePart(part).catch(() => {});
        }}
        type="button"
      >
        <CopyIcon className="size-4" />
      </button>
      {onRegenerate && <RegenerateButton onRegenerate={onRegenerate} />}
    </div>
  );
}

const ImageImpl: ImageMessagePartComponent = (props) => {
  const { image, filename, status } = props;

  if (status?.type === "running") {
    return (
      <ImageRoot>
        <ImageGenerating />
        <ImageFilename>{filename}</ImageFilename>
      </ImageRoot>
    );
  }

  if (status?.type === "incomplete" && status.reason === "content-filter") {
    return (
      <ImageRoot>
        <ImageContentFilterError reason="The provider blocked this image." />
      </ImageRoot>
    );
  }

  return (
    <ImageRoot>
      <ImageZoom alt={filename || "Image content"} src={image}>
        <ImagePreview alt={filename || "Image content"} src={image} />
      </ImageZoom>
      <ImageFilename>{filename}</ImageFilename>
    </ImageRoot>
  );
};

const Image = memo(ImageImpl) as unknown as ImageMessagePartComponent & {
  Root: typeof ImageRoot;
  Preview: typeof ImagePreview;
  Filename: typeof ImageFilename;
  Zoom: typeof ImageZoom;
  Actions: typeof ImageActions;
  Generating: typeof ImageGenerating;
  ContentFilterError: typeof ImageContentFilterError;
};

Image.displayName = "Image";
Image.Root = ImageRoot;
Image.Preview = ImagePreview;
Image.Filename = ImageFilename;
Image.Zoom = ImageZoom;
Image.Actions = ImageActions;
Image.Generating = ImageGenerating;
Image.ContentFilterError = ImageContentFilterError;

export {
  Image,
  ImageActions,
  ImageContentFilterError,
  ImageFilename,
  ImageGenerating,
  ImagePreview,
  ImageRoot,
  ImageZoom,
  imageVariants,
};
