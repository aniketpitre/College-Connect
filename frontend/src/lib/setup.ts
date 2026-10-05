import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "./api";

export type RecordStatus = "active" | "archived";

interface Base {
  id: string;
  status: RecordStatus;
}
export interface AcademicYear extends Base {
  name: string;
  start_date: string;
  end_date: string;
  is_current: boolean;
}
export interface Department extends Base {
  code: string;
  name: string;
}
export interface Programme extends Base {
  code: string;
  name: string;
  department_id: string;
  level: string;
  duration_years: number;
  semesters_per_year: number;
  year_labels: string[];
}
export interface Division extends Base {
  programme_id: string;
  year_of_study: number;
  name: string;
  capacity: number | null;
}
export interface Subject extends Base {
  programme_id: string;
  semester: number;
  code: string;
  name: string;
  credits: number;
  type: string;
  max_internal: number;
  max_external: number;
}
export interface Category extends Base {
  code: string;
  name: string;
  reserved_percent: number | null;
}
export interface Holiday extends Base {
  academic_year_id: string;
  date: string;
  name: string;
}
export interface Institution {
  name: string;
  short_name: string;
  address: string;
  phone: string;
  email: string | null;
  website: string;
  university: string;
  college_code: string;
  receipt_prefix: string;
  certificate_prefix: string;
  attendance_min_percent: number;
  attendance_warn_percent: number;
}
export interface SetupOverview {
  institution: Institution;
  current_year: AcademicYear | null;
  academic_years: AcademicYear[];
  departments: Department[];
  programmes: Programme[];
  divisions: Division[];
  categories: Category[];
}

export const SETUP_KEY = ["setup"] as const;

export function useSetup() {
  return useQuery({ queryKey: SETUP_KEY, queryFn: () => apiFetch<SetupOverview>("/setup"), staleTime: 60_000 });
}

export function useSubjects(programmeId: string | undefined) {
  return useQuery({
    queryKey: [...SETUP_KEY, "subjects", programmeId],
    queryFn: () => apiFetch<Subject[]>(`/setup/subjects?programme_id=${programmeId}`),
    enabled: Boolean(programmeId),
  });
}

export function useHolidays(yearId: string | undefined) {
  return useQuery({
    queryKey: [...SETUP_KEY, "holidays", yearId],
    queryFn: () => apiFetch<Holiday[]>(`/setup/holidays?academic_year_id=${yearId}`),
    enabled: Boolean(yearId),
  });
}

/** POST /setup/<path> or PATCH /setup/<path>/<id>; refreshes every setup query. */
export function useSaveRecord(path: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, body }: { id?: string; body: Record<string, unknown> }) =>
      apiFetch<Base>(id ? `/setup/${path}/${id}` : `/setup/${path}`, { method: id ? "PATCH" : "POST", body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: SETUP_KEY }),
  });
}

export function useSetupAction<T = unknown>() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ path, method = "POST", body }: { path: string; method?: string; body?: unknown }) =>
      apiFetch<T>(`/setup/${path}`, { method, body: body === undefined ? undefined : JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: SETUP_KEY }),
  });
}

/** "BCA · SY · A" */
export function classLabel(setup: SetupOverview | undefined, programmeId?: string | null, year?: number | null, divisionId?: string | null) {
  const programme = setup?.programmes.find((p) => p.id === programmeId);
  if (!programme) return "";
  const parts = [programme.code];
  if (year) parts.push(programme.year_labels[year - 1] ?? `Year ${year}`);
  const division = setup?.divisions.find((d) => d.id === divisionId);
  if (division) parts.push(division.name);
  return parts.join(" · ");
}
