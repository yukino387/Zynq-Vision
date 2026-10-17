<script setup lang="ts">
import { chinese } from "@vision/shared";
import { computed, ref, watch } from "vue";
import { useRoute } from "vue-router";
import type { Inspection } from "../types";
import { useList } from "../composables/useList";
import Status from "../components/Status.vue";
import AsyncState from "../components/AsyncState.vue";
import Pager from "../components/Pager.vue";
import SortableTh from "../components/SortableTh.vue";

const advanced = ref(false);
function resetFilters() {
  list.search.value = "";
  list.source.value = "";
  list.from.value = "";
  list.to.value = "";
  list.filter();
}
const route = useRoute(),
  endpoint = ref("/inspections"),
  list = useList<Inspection>(endpoint),
  tab = computed(() =>
    String(route.params.tab || route.meta.defaultTab || "queue"),
  );

/** 待办 tab 只要待复核的；「全部」不加结果筛选。
 *  useList 创建时已按空筛选取过一次，这里按 tab 纠正并重载。 */
function applyTab() {
  list.result.value = tab.value === "queue" ? "REVIEW" : "";
  list.reviewed.value = tab.value === "queue" ? "false" : "";
  list.filter();
}
watch(tab, applyTab);
applyTab();
</script>
<template>
  <div class="page-heading">
    <div>
      <h1>{{ tab === "queue" ? "待复核记录" : "全部检测记录" }}</h1>
    </div>
    <RouterLink :to="{ name: 'workbench' }">返回工作台</RouterLink>
  </div>

  <form class="toolbar" @submit.prevent="list.filter">
    <!-- 检测没有名称字段，search 只匹配编号 -->
    <input
      v-model="list.search.value"
      type="search"
      placeholder="搜索检测编号…"
      aria-label="搜索检测编号"
    /><button
      type="button"
      :aria-expanded="advanced"
      @click="advanced = !advanced"
    >
      {{ advanced ? "收起筛选" : "更多筛选" }}</button
    ><button
      v-if="
        list.search.value ||
        list.source.value ||
        list.from.value ||
        list.to.value
      "
      type="button"
      @click="resetFilters"
    >
      清空条件
    </button>
    <div v-if="advanced" class="filter-details">
      <label
        >来源<select v-model="list.source.value">
          <option value="">全部来源</option>
          <option value="BOARD">{{ chinese("BOARD") }}</option>
          <option value="SIMULATION">{{ chinese("SIMULATION") }}</option>
        </select></label
      >
      <label
        >开始时间<input type="datetime-local" v-model="list.from.value"
      /></label>
      <label
        >结束时间<input type="datetime-local" v-model="list.to.value"
      /></label>
    </div>
    <button
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
    >
      查询</button
    ><button
      type="button"
      :class="{ busy: list.loading.value }"
      :disabled="list.loading.value"
      @click="list.load"
    >
      刷新
    </button>
  </form>

  <AsyncState
    :loading="list.loading.value"
    :error="list.error.value"
    :empty="!list.items.value.length"
    @retry="list.load"
    ><div class="panel table-wrap">
      <table>
        <thead>
          <tr>
            <th>检测编号</th>
            <SortableTh
              field="source"
              label="采样来源"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <SortableTh
              field="createdAt"
              label="时间"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <th>模型版本</th>
            <th>推理 ms</th>
            <SortableTh
              field="result"
              label="设备判定"
              :active="list.sort.value"
              :order="list.order.value"
              @sort="list.sortBy"
            />
            <th>人工复核</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="i in list.items.value"
            :key="i.id"
            class="clickable"
            @click="
              $router.push({
                name: 'inspection',
                params: { id: i.id },
                query: tab === 'queue' ? { queue: '1' } : {},
              })
            "
          >
            <td class="mono">{{ i.id.slice(-10) }}</td>
            <td>
              <span
                class="tag"
                :class="{ simulated: i.source === 'SIMULATION' }"
                >{{ chinese(i.source) }}</span
              >
            </td>
            <td>{{ new Date(i.createdAt).toLocaleString() }}</td>
            <td class="mono" :class="{ muted: !i.modelVersion }">
              {{ i.modelVersion ?? "未上报" }}
            </td>
            <td class="mono">{{ i.latency?.toFixed(2) ?? "—" }}</td>
            <td>
              <Status chip :value="i.result" />
            </td>
            <td>
              {{
                i.reviews.length
                  ? "已复核"
                  : i.result === "REVIEW"
                    ? "待复核"
                    : "—"
              }}
            </td>
            <td>
              <RouterLink
                class="table-action"
                @click.stop
                :to="{
                  name: 'inspection',
                  params: { id: i.id },
                  query: tab === 'queue' ? { queue: '1' } : {},
                }"
                >{{ tab === "queue" ? "立即复核" : "查看详情" }}</RouterLink
              >
            </td>
          </tr>
        </tbody>
      </table>
    </div></AsyncState
  >
  <Pager
    :page="list.page.value"
    :total="list.total.value"
    :page-size="list.pageSize.value"
    @update:page="
      (p) => {
        list.page.value = p;
        list.load();
      }
    "
    @update:page-size="list.setPageSize"
  />
</template>
