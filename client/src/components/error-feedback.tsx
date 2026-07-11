import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { toast } from "sonner";

import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { asAppError, type ApiError } from "@/lib/errors";

interface ErrorFeedback {
  notify(error: unknown): ApiError;
}

const fallbackErrorFeedback: ErrorFeedback = {
  notify: (unknownError) => asAppError(unknownError),
};

const ErrorFeedbackContext = createContext<ErrorFeedback | null>(null);

export function ErrorFeedbackProvider({ children }: { children: ReactNode }) {
  const [dialogError, setDialogError] = useState<ApiError | null>(null);

  const notify = useCallback((unknownError: unknown) => {
    const error = asAppError(unknownError);
    if (error.presentation === "toast") {
      toast.error(error.message);
    } else if (error.presentation === "dialog") {
      setDialogError(error);
    }
    return error;
  }, []);

  return (
    <ErrorFeedbackContext.Provider value={{ notify }}>
      {children}
      <AlertDialog
        onOpenChange={(open) => {
          if (!open) setDialogError(null);
        }}
        open={dialogError !== null}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Something needs your attention</AlertDialogTitle>
            <AlertDialogDescription>
              {dialogError?.message ?? "The request could not be completed."}
              {dialogError?.requestId ? ` Reference: ${dialogError.requestId}` : ""}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogAction onClick={() => setDialogError(null)}>
              Close
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </ErrorFeedbackContext.Provider>
  );
}

export function useErrorFeedback(): ErrorFeedback {
  const context = useContext(ErrorFeedbackContext);
  if (!context) {
    return fallbackErrorFeedback;
  }
  return context;
}
