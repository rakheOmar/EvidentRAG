import { AssistantRuntimeProvider, useAui } from "@assistant-ui/react";
import { AuiProvider } from "@assistant-ui/store";
import { Tick02Icon } from "@hugeicons/core-free-icons";
import { HugeiconsIcon } from "@hugeicons/react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  type ColumnDef,
  flexRender,
  getCoreRowModel,
  type Header,
  useReactTable,
} from "@tanstack/react-table";
import {
  FileTextIcon,
  FileUpIcon,
  LoaderCircleIcon,
  PanelLeftIcon,
  RefreshCwIcon,
  SearchIcon,
  ShareIcon,
  Trash2Icon,
  TriangleAlertIcon,
} from "lucide-react";
import {
  type ChangeEvent,
  type DragEvent,
  type MouseEvent,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import { TooltipIconButton } from "@/components/assistant-ui/tooltip-icon-button";
import {
  AppShell,
  MobileSidebar,
  useSidebarState,
} from "@/components/chat/chat-sidebar";
import { useErrorFeedback } from "@/components/error-feedback";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { useEvidentRuntime } from "@/hooks/use-evident-runtime";
import {
  deleteDocument,
  fetchDocuments,
  queryKeys,
  uploadDocument,
} from "@/lib/api";
import type { DocumentRecord } from "@/lib/types";

const ACCEPTED_FILE_TYPES = ".pdf,application/pdf";
const MAX_UPLOAD_SIZE = 25 * 1024 * 1024;

interface IngestionProgress {
  progress: number;
  stage: string;
}

const DOCUMENT_HEADER_CLASSES: Record<string, string> = {
  actions: "h-9 w-10 px-0 text-right",
  byte_size:
    "hidden h-9 w-19 text-right text-muted-foreground text-xs uppercase tracking-[0.08em] sm:table-cell",
  original_filename:
    "h-9 w-full px-0 text-muted-foreground text-xs uppercase tracking-[0.08em]",
  progress:
    "hidden h-9 w-20 text-center text-muted-foreground text-xs uppercase tracking-[0.08em] sm:table-cell",
  status:
    "hidden h-9 w-30 text-muted-foreground text-xs uppercase tracking-[0.08em] sm:table-cell",
  updated_at:
    "hidden h-9 w-30 text-muted-foreground text-xs uppercase tracking-[0.08em] sm:table-cell",
};

const DOCUMENT_CELL_CLASSES: Record<string, string> = {
  actions:
    "w-10 rounded-r-xl px-2 text-right transition-colors duration-300 ease-out group-focus-within:bg-muted/35 group-hover:bg-muted/35",
  byte_size:
    "hidden text-muted-foreground text-sm tabular-nums transition-colors duration-300 ease-out group-focus-within:bg-muted/35 group-hover:bg-muted/35 sm:table-cell",
  original_filename:
    "min-w-0 whitespace-normal rounded-l-xl px-2 py-2.5 transition-colors duration-300 ease-out group-focus-within:bg-muted/35 group-hover:bg-muted/35",
  progress:
    "hidden w-20 text-center transition-colors duration-300 ease-out group-focus-within:bg-muted/35 group-hover:bg-muted/35 sm:table-cell",
  status:
    "hidden min-w-0 max-w-30 overflow-hidden transition-colors duration-300 ease-out group-focus-within:bg-muted/35 group-hover:bg-muted/35 sm:table-cell",
  updated_at:
    "hidden truncate text-muted-foreground text-sm transition-colors duration-300 ease-out group-focus-within:bg-muted/35 group-hover:bg-muted/35 sm:table-cell",
};

function renderDocumentHeader(
  header: Header<DocumentRecord, unknown>
): ReactNode {
  if (header.isPlaceholder) {
    return null;
  }
  if (header.column.id === "actions") {
    return <span className="sr-only">Actions</span>;
  }
  return flexRender(header.column.columnDef.header, header.getContext());
}

type DocumentFilter = "all" | "processing" | "ready";

const documentFilters: { label: string; value: DocumentFilter }[] = [
  { label: "All", value: "all" },
  { label: "Processing", value: "processing" },
  { label: "Ready", value: "ready" },
];

function isIngesting(document: DocumentRecord): boolean {
  return (
    document.status === "queued" ||
    document.status === "processing" ||
    document.status === "publishing"
  );
}

function fallbackProgress(document: DocumentRecord): IngestionProgress {
  if (document.status === "queued") {
    return { progress: 5, stage: "Queued" };
  }
  if (document.status === "publishing") {
    return { progress: 95, stage: "Publishing" };
  }
  return { progress: 35, stage: "Processing" };
}

function formatBytes(bytes: number | null): string {
  if (bytes === null) {
    return "Unknown size";
  }
  if (bytes < 1024 * 1024) {
    return `${Math.ceil(bytes / 1024)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
}

function statusDetails(status: string): {
  label: string;
  variant: "destructive" | "outline" | "secondary";
} {
  switch (status) {
    case "ready":
    case "ready_with_warnings":
      return {
        label: status === "ready" ? "Ready" : "Ready with warnings",
        variant: "secondary",
      };
    case "failed":
      return { label: "Failed", variant: "destructive" };
    case "deleted":
      return { label: "Deleted", variant: "outline" };
    default:
      return {
        label: status === "queued" ? "Queued" : "Processing",
        variant: "outline",
      };
  }
}

function matchesFilter(
  document: DocumentRecord,
  filter: DocumentFilter
): boolean {
  if (filter === "all") {
    return true;
  }
  if (filter === "processing") {
    return isIngesting(document);
  }
  return (
    document.status === "ready" || document.status === "ready_with_warnings"
  );
}

function useIngestionProgress(documents: DocumentRecord[]) {
  const queryClient = useQueryClient();
  const [progressByDocument, setProgressByDocument] = useState<
    Record<string, IngestionProgress>
  >({});
  const sourcesRef = useRef(new Map<string, EventSource>());

  useEffect(() => {
    const activeIds = new Set(
      documents.filter(isIngesting).map((document) => document.id)
    );
    for (const [documentId, source] of sourcesRef.current) {
      if (!activeIds.has(documentId)) {
        source.close();
        sourcesRef.current.delete(documentId);
      }
    }
    for (const document of documents.filter(isIngesting)) {
      if (sourcesRef.current.has(document.id)) {
        continue;
      }
      const source = new EventSource(`/api/v1/documents/${document.id}/events`);
      sourcesRef.current.set(document.id, source);
      source.addEventListener("progress", (event: MessageEvent<string>) => {
        const payload = JSON.parse(event.data) as IngestionProgress;
        setProgressByDocument((current) => ({
          ...current,
          [document.id]: payload,
        }));
      });
      source.addEventListener("done", () => {
        source.close();
        sourcesRef.current.delete(document.id);
        queryClient.invalidateQueries({ queryKey: queryKeys.documents });
      });
    }
  }, [documents, queryClient]);

  useEffect(() => () => {
    for (const source of sourcesRef.current.values()) {
      source.close();
    }
    sourcesRef.current.clear();
  });

  return progressByDocument;
}

function IngestionProgressDial({ value }: { value: number }) {
  const radius = 11;
  const circumference = 2 * Math.PI * radius;
  const progress = Math.min(100, Math.max(0, value));
  const offset = circumference - (progress / 100) * circumference;

  return (
    <div
      aria-label={`Ingestion progress: ${progress}%`}
      aria-valuemax={100}
      aria-valuemin={0}
      aria-valuenow={progress}
      className="relative size-7 shrink-0"
      role="progressbar"
    >
      <svg
        aria-hidden="true"
        className="size-7 -rotate-90"
        fill="none"
        viewBox="0 0 28 28"
      >
        <circle
          className="stroke-muted"
          cx="14"
          cy="14"
          r={radius}
          strokeWidth="3"
        />
        <circle
          className="stroke-foreground transition-[stroke-dashoffset] duration-500 ease-out"
          cx="14"
          cy="14"
          r={radius}
          strokeDasharray={circumference}
          strokeDashoffset={offset}
          strokeLinecap="round"
          strokeWidth="3"
        />
      </svg>
      <span className="absolute inset-0 flex items-center justify-center font-mono text-[8px] text-muted-foreground tabular-nums">
        {progress}%
      </span>
    </div>
  );
}

function DocumentNameCell({ document }: { document: DocumentRecord }) {
  return (
    <div className="min-w-0">
      <div className="flex min-w-0 items-center gap-3">
        <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-muted text-muted-foreground ring-1 ring-foreground/10">
          <FileTextIcon className="size-4" />
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex min-w-0 items-center gap-2">
            <p className="truncate font-medium text-sm">
              {document.original_filename ?? document.title}
            </p>
            {document.is_current ? (
              <Badge variant="secondary">Current</Badge>
            ) : null}
          </div>
          <p className="mt-0.5 truncate text-muted-foreground text-xs sm:hidden">
            {formatDate(document.updated_at)} /{" "}
            {formatBytes(document.byte_size)}
          </p>
        </div>
      </div>
      {document.error_message ? (
        <p className="mt-1 pl-11 text-destructive text-xs">
          {document.error_message}
        </p>
      ) : null}
    </div>
  );
}

function DocumentTable({
  documents,
  onDelete,
  progressByDocument,
}: {
  documents: DocumentRecord[];
  onDelete: (document: DocumentRecord) => void;
  progressByDocument: Record<string, IngestionProgress>;
}) {
  const columns = useMemo<ColumnDef<DocumentRecord>[]>(
    () => [
      {
        accessorKey: "original_filename",
        cell: ({ row }) => <DocumentNameCell document={row.original} />,
        header: "Name",
      },
      {
        id: "progress",
        cell: ({ row }) => {
          if (isIngesting(row.original)) {
            const progress =
              progressByDocument[row.original.id] ??
              fallbackProgress(row.original);
            return (
              <div className="flex justify-center">
                <IngestionProgressDial value={progress.progress} />
              </div>
            );
          }
          if (
            row.original.status !== "ready" &&
            row.original.status !== "ready_with_warnings"
          ) {
            return null;
          }
          return (
            <div className="flex justify-center" title="Ingestion complete">
              <HugeiconsIcon
                aria-label="Ingestion complete"
                className="size-5 text-emerald-500"
                icon={Tick02Icon}
                strokeWidth={2.4}
              />
            </div>
          );
        },
        header: "Progress",
      },
      {
        accessorKey: "status",
        cell: ({ row }) => {
          const status = statusDetails(row.original.status);
          return (
            <Badge
              className="max-w-full"
              title={status.label}
              variant={status.variant}
            >
              <span className="min-w-0 truncate">{status.label}</span>
            </Badge>
          );
        },
        header: "Status",
      },
      {
        accessorKey: "updated_at",
        cell: ({ row }) => formatDate(row.original.updated_at),
        header: "Modified",
      },
      {
        accessorKey: "byte_size",
        cell: ({ row }) => formatBytes(row.original.byte_size),
        header: "Size",
      },
      {
        id: "actions",
        cell: ({ row }) => (
          <Button
            aria-label={`Delete ${row.original.original_filename ?? row.original.title}`}
            className="size-10 text-muted-foreground transition-[color,transform,background-color] duration-200 hover:bg-destructive/10 hover:text-destructive active:scale-[0.96]"
            onClick={() => onDelete(row.original)}
            size="icon"
            title="Delete document"
            variant="ghost"
          >
            <Trash2Icon className="size-4" />
          </Button>
        ),
        header: "Actions",
      },
    ],
    [onDelete, progressByDocument]
  );
  const table = useReactTable({
    columns,
    data: documents,
    getCoreRowModel: getCoreRowModel(),
  });

  return (
    <Table
      aria-label="Documents"
      className="table-fixed"
      containerClassName="overflow-x-hidden"
    >
      <TableHeader className="[&_tr]:border-b-0">
        {table.getHeaderGroups().map((headerGroup) => (
          <TableRow className="hover:bg-transparent" key={headerGroup.id}>
            {headerGroup.headers.map((header) => (
              <TableHead
                className={DOCUMENT_HEADER_CLASSES[header.column.id]}
                key={header.id}
              >
                {renderDocumentHeader(header)}
              </TableHead>
            ))}
          </TableRow>
        ))}
      </TableHeader>
      <TableBody>
        {table.getRowModel().rows.map((row) => (
          <TableRow className="group min-h-14 border-border/70" key={row.id}>
            {row.getVisibleCells().map((cell) => (
              <TableCell
                className={DOCUMENT_CELL_CLASSES[cell.column.id]}
                key={cell.id}
              >
                {flexRender(cell.column.columnDef.cell, cell.getContext())}
              </TableCell>
            ))}
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}

function DocumentsScreen() {
  const { collapsed: sidebarCollapsed, setCollapsed: setSidebarCollapsed } =
    useSidebarState();
  const { notify } = useErrorFeedback();
  const queryClient = useQueryClient();
  const [dragging, setDragging] = useState(false);
  const [filter, setFilter] = useState<DocumentFilter>("all");
  const [searchTerm, setSearchTerm] = useState("");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [documentToDelete, setDocumentToDelete] =
    useState<DocumentRecord | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const documentsQuery = useQuery({
    queryFn: fetchDocuments,
    queryKey: queryKeys.documents,
    refetchInterval: 2000,
  });
  const uploadMutation = useMutation({
    mutationFn: (files: File[]) =>
      Promise.all(files.map((file) => uploadDocument(file))),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.documents }),
  });
  const deleteMutation = useMutation({
    mutationFn: deleteDocument,
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: queryKeys.documents }),
  });
  const documents = documentsQuery.data?.items ?? [];
  const progressByDocument = useIngestionProgress(documents);
  const visibleDocuments = useMemo(() => {
    const normalizedQuery = searchTerm.trim().toLowerCase();
    return documents.filter((document) => {
      const name = (document.original_filename ?? document.title).toLowerCase();
      return matchesFilter(document, filter) && name.includes(normalizedQuery);
    });
  }, [documents, filter, searchTerm]);

  const uploadFiles = useCallback(
    async (files: File[]) => {
      const invalidFile = files.find(
        (file) => file.type !== "application/pdf" || file.size > MAX_UPLOAD_SIZE
      );
      if (invalidFile) {
        setUploadError(
          `${invalidFile.name} must be a PDF no larger than 25 MB.`
        );
        return;
      }
      setUploadError(null);
      try {
        await uploadMutation.mutateAsync(files);
      } catch (error) {
        const appError = notify(error);
        setUploadError(appError.message);
      }
    },
    [notify, uploadMutation]
  );

  const handleFiles = useCallback(
    async (event: ChangeEvent<HTMLInputElement>) => {
      const files = Array.from(event.target.files ?? []);
      event.target.value = "";
      if (files.length > 0) {
        await uploadFiles(files);
      }
    },
    [uploadFiles]
  );
  const handleDrop = useCallback(
    async (event: DragEvent<HTMLButtonElement>) => {
      event.preventDefault();
      setDragging(false);
      const files = Array.from(event.dataTransfer.files);
      if (files.length > 0) {
        await uploadFiles(files);
      }
    },
    [uploadFiles]
  );
  const handleDragEnter = useCallback(() => setDragging(true), []);
  const handleDragLeave = useCallback(() => setDragging(false), []);
  const handleDragOver = useCallback((event: DragEvent<HTMLButtonElement>) => {
    event.preventDefault();
  }, []);
  const handleUploadClick = useCallback(
    () => fileInputRef.current?.click(),
    []
  );
  const handleSearchChange = useCallback(
    (event: ChangeEvent<HTMLInputElement>) => setSearchTerm(event.target.value),
    []
  );
  const handleFilterChange = useCallback(
    (event: MouseEvent<HTMLButtonElement>) => {
      const value = event.currentTarget.dataset.filter;
      if (value === "all" || value === "processing" || value === "ready") {
        setFilter(value);
      }
    },
    []
  );
  const handleRefetch = useCallback(async () => {
    await documentsQuery.refetch();
  }, [documentsQuery]);
  const handleDialogOpenChange = useCallback((open: boolean) => {
    if (!open) {
      setDocumentToDelete(null);
    }
  }, []);
  const handleDeleteConfirm = useCallback(() => {
    if (!documentToDelete) {
      return;
    }
    deleteMutation.mutate(documentToDelete.id, {
      onError: notify,
      onSettled: () => setDocumentToDelete(null),
    });
  }, [deleteMutation, documentToDelete, notify]);
  const handleToggleSidebar = useCallback(
    () => setSidebarCollapsed((current) => !current),
    [setSidebarCollapsed]
  );

  let documentListContent: ReactNode;
  if (documentsQuery.isLoading) {
    documentListContent = (
      <div className="flex min-h-36 items-center justify-center gap-2 text-muted-foreground text-sm">
        <LoaderCircleIcon className="size-4 animate-spin" /> Loading documents
      </div>
    );
  } else if (documents.length === 0) {
    documentListContent = (
      <button
        aria-controls="document-upload-input"
        className={`mt-5 flex min-h-64 w-full cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed bg-transparent p-8 text-center outline-none transition-[background-color,border-color,transform] focus-visible:border-primary focus-visible:bg-primary/5 ${dragging ? "border-primary bg-primary/5" : "border-border hover:bg-muted/45"}`}
        onClick={handleUploadClick}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        type="button"
      >
        <div className="mb-3 flex size-10 items-center justify-center rounded-xl bg-muted text-muted-foreground ring-1 ring-foreground/10">
          <FileUpIcon className="size-5" />
        </div>
        <span className="font-medium text-sm">
          Drop PDFs here or choose files
        </span>
        <span className="mt-1 text-muted-foreground text-sm">
          Files are processed securely and become available when ready.
        </span>
      </button>
    );
  } else if (visibleDocuments.length === 0) {
    documentListContent = (
      <div className="flex min-h-40 items-center justify-center text-muted-foreground text-sm">
        No documents match this view.
      </div>
    );
  } else {
    documentListContent = (
      <DocumentTable
        documents={visibleDocuments}
        onDelete={setDocumentToDelete}
        progressByDocument={progressByDocument}
      />
    );
  }

  return (
    <main className="min-w-0 flex-1 overflow-y-auto rounded-lg bg-background">
      <header className="flex h-12 shrink-0 items-center gap-2 px-4">
        <MobileSidebar />
        <TooltipIconButton
          className="hidden size-8 md:flex"
          onClick={handleToggleSidebar}
          side="bottom"
          size="icon"
          tooltip={sidebarCollapsed ? "Show sidebar" : "Hide sidebar"}
          variant="ghost"
        >
          <PanelLeftIcon className="size-4" />
        </TooltipIconButton>
        <span className="min-w-0 truncate font-medium text-sm">Documents</span>
        <TooltipIconButton
          className="ml-auto size-8"
          disabled
          side="bottom"
          size="icon"
          tooltip="Share"
          variant="ghost"
        >
          <ShareIcon className="size-4" />
        </TooltipIconButton>
      </header>
      <div className="mx-auto flex w-full max-w-[920px] flex-col px-4 pt-5 pb-8 md:px-6 md:pt-10 md:pb-12">
        <div className="flex min-h-12 flex-wrap items-center gap-3 md:gap-4">
          <div className="relative min-w-52 flex-1 sm:max-w-60 md:flex-none">
            <SearchIcon className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <input
              aria-label="Search documents"
              className="h-9 w-full rounded-full border bg-background py-2 pr-3 pl-9 text-sm outline-none transition-[border-color,box-shadow] placeholder:text-muted-foreground focus:border-foreground/40 focus:ring-2 focus:ring-ring/30"
              onChange={handleSearchChange}
              placeholder="Search"
              type="search"
              value={searchTerm}
            />
          </div>
          <Button
            className="active:scale-[0.96]"
            disabled={uploadMutation.isPending}
            onClick={handleUploadClick}
          >
            {uploadMutation.isPending ? (
              <LoaderCircleIcon className="animate-spin" />
            ) : (
              <FileUpIcon />
            )}
            New
          </Button>
          <input
            accept={ACCEPTED_FILE_TYPES}
            className="sr-only"
            disabled={uploadMutation.isPending}
            id="document-upload-input"
            multiple
            onChange={handleFiles}
            ref={fileInputRef}
            type="file"
          />
        </div>

        <section className="sticky top-0 z-10 mt-6 border-y bg-background py-2">
          <div className="flex min-h-10 items-center gap-1 overflow-x-auto">
            {documentFilters.map((option) => (
              <Button
                aria-current={filter === option.value ? "page" : undefined}
                className={
                  filter === option.value
                    ? "bg-muted shadow-[0_0_0_1px_var(--border)] hover:bg-muted"
                    : "text-muted-foreground"
                }
                data-filter={option.value}
                key={option.value}
                onClick={handleFilterChange}
                size="sm"
                variant="ghost"
              >
                {option.label}
              </Button>
            ))}
            <span className="ml-auto shrink-0 pr-1 text-muted-foreground text-xs tabular-nums">
              {visibleDocuments.length} of {documentsQuery.data?.total ?? 0}
            </span>
          </div>
        </section>

        {uploadError ? (
          <p className="mt-3 text-destructive text-sm">{uploadError}</p>
        ) : null}
        <section className="mt-2">
          {documentListContent}
          {documentsQuery.isError ? (
            <Button className="mt-4" onClick={handleRefetch} variant="outline">
              <RefreshCwIcon /> Try again
            </Button>
          ) : null}
        </section>
      </div>

      <AlertDialog
        onOpenChange={handleDialogOpenChange}
        open={documentToDelete !== null}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <TriangleAlertIcon className="size-5 text-destructive" />
            <AlertDialogTitle>Remove this document?</AlertDialogTitle>
            <AlertDialogDescription>
              {documentToDelete?.original_filename ?? documentToDelete?.title}{" "}
              and every version of this source will stop being used for
              retrieval.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>Cancel</AlertDialogCancel>
            <AlertDialogAction
              disabled={deleteMutation.isPending}
              onClick={handleDeleteConfirm}
              variant="destructive"
            >
              {deleteMutation.isPending ? (
                <LoaderCircleIcon className="animate-spin" />
              ) : (
                <Trash2Icon />
              )}
              Remove document
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </main>
  );
}

function DocumentsRuntime() {
  const { runtime } = useEvidentRuntime();

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <AppShell>
        <DocumentsScreen />
      </AppShell>
    </AssistantRuntimeProvider>
  );
}

function AuiProviderWrapper({ children }: { children: ReactNode }) {
  const rootClient = useAui({}, { parent: null });
  return <AuiProvider value={rootClient}>{children}</AuiProvider>;
}

export function DocumentsPage() {
  return (
    <AuiProviderWrapper>
      <DocumentsRuntime />
    </AuiProviderWrapper>
  );
}
