type LogFields = Record<string, unknown>;

const serviceContext = {
  environment: import.meta.env.MODE,
  service: "evidentrag-client",
  version: import.meta.env.VITE_SERVICE_VERSION ?? "unknown",
};

function emit(level: "error" | "info", fields: LogFields): void {
  const payload = {
    ...serviceContext,
    timestamp: new Date().toISOString(),
    ...fields,
  };
  console[level](payload);
}

export const logger = {
  error: (fields: LogFields) => emit("error", fields),
  info: (fields: LogFields) => emit("info", fields),
};
