import { ref, watch, type Ref } from "vue";
import type { Page } from "@vision/contracts";
import { api, errorText } from "../api";
export function useList<T>(endpoint: Ref<string>) {
  const items = ref<T[]>([]) as Ref<T[]>,
    loading = ref(false),
    error = ref(""),
    total = ref(0),
    page = ref(1),
    pageSize = ref(20),
    search = ref(""),
    status = ref(""),
    result = ref(""),
    reviewed = ref(""),
    realOnly = ref(""),
    annotation = ref(""),
    source = ref(""),
    from = ref(""),
    to = ref(""),
    /** 排序字段必须在该路由的 sort 白名单里，否则接口返回 400 */
    sort = ref("createdAt"),
    order = ref<"asc" | "desc">("desc");
  let generation = 0;
  async function load() {
    const request = ++generation;
    loading.value = true;
    error.value = "";
    try {
      const q = new URLSearchParams({
        page: String(page.value),
        pageSize: String(pageSize.value),
      });
      for (const [k, v] of Object.entries({
        search: search.value,
        status: status.value,
        result: result.value,
        reviewed: reviewed.value,
        realOnly: realOnly.value,
        annotation: annotation.value,
        source: source.value,
        from: from.value ? new Date(from.value).toISOString() : "",
        to: to.value ? new Date(to.value).toISOString() : "",
        sort: sort.value,
        order: order.value,
      }))
        if (v) q.set(k, v);
      const response = await api<Page<T>>(`${endpoint.value}?${q}`);
      if (request !== generation) return;
      items.value = response.items;
      total.value = response.total;
    } catch (e) {
      if (request === generation) error.value = errorText(e);
    } finally {
      if (request === generation) loading.value = false;
    }
  }
  /** 每页条数由控件改；接口上限 100 */
  function setPageSize(size: number) {
    pageSize.value = size;
    page.value = 1;
    void load();
  }
  function filter() {
    page.value = 1;
    void load();
  }
  /** 点同一列切换升降序，换列则回到降序（时间类默认看最新）。 */
  function sortBy(field: string) {
    if (sort.value === field)
      order.value = order.value === "asc" ? "desc" : "asc";
    else {
      sort.value = field;
      order.value = "desc";
    }
    page.value = 1;
    void load();
  }
  watch(
    endpoint,
    () => {
      page.value = 1;
      search.value = "";
      status.value = "";
      result.value = "";
      reviewed.value = "";
      void load();
    },
    { immediate: true },
  );
  return {
    items,
    loading,
    error,
    total,
    page,
    pageSize,
    search,
    status,
    result,
    reviewed,
    realOnly,
    annotation,
    source,
    from,
    to,
    sort,
    order,
    sortBy,
    load,
    filter,
    setPageSize,
  };
}
