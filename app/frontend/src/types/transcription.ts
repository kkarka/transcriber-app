export type AppState =
  | "upload"
  | "processing"
  | "result"

export interface JobResponse {
  job_id: string
  status: string
}

export interface StatusResponse {
  status: string
  result?: string
}