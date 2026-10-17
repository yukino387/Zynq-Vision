import { listSchema } from "@vision/contracts";
import { DomainError } from "./errors.js";
export function listing(
  query: unknown,
  fields: string[] = ["name", "status", "createdAt", "updatedAt"],
) {
  const q = listSchema.parse(query);
  if (!fields.includes(q.sort))
    throw new DomainError(
      "VALIDATION_ERROR",
      `Unsupported sort ${q.sort}`,
      400,
    );
  const where: Record<string, unknown> = {};
  if (q.search)
    where.OR = [
      { id: { contains: q.search } },
      ...(fields.includes("name") ? [{ name: { contains: q.search } }] : []),
    ];
  if (q.status && fields.includes("status")) where.status = q.status;
  if (q.source && fields.includes("source")) where.source = q.source;
  if (q.from || q.to)
    where.createdAt = {
      ...(q.from ? { gte: new Date(q.from) } : {}),
      ...(q.to ? { lte: new Date(q.to) } : {}),
    };
  for (const key of ["deviceId", "taskId", "stationId", "result"] as const)
    if (q[key] && fields.includes(key)) where[key] = q[key];
  return {
    q,
    where,
    args: {
      where,
      skip: (q.page - 1) * q.pageSize,
      take: q.pageSize,
      orderBy: { [q.sort]: q.order },
    },
  };
}
export function page<T>(
  items: T[],
  total: number,
  q: { page: number; pageSize: number },
) {
  return { items, total, page: q.page, pageSize: q.pageSize };
}
