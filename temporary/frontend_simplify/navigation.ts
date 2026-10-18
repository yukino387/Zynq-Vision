import type { RouteRecordRaw } from "vue-router";
import type { Role } from "@vision/contracts";
import Overview from "./views/Overview.vue";
import Operations from "./views/Operations.vue";
import Records from "./views/Records.vue";
import InspectionDetail from "./views/InspectionDetail.vue";
import Data from "./views/Data.vue";
import Models from "./views/Models.vue";
import Devices from "./views/Devices.vue";
import System from "./views/System.vue";
import NotFound from "./views/NotFound.vue";
import Access from "./views/Access.vue";

export interface TabMeta {
  tab: string;
  label: string;
  /** 省略表示全部角色可见 */
  roles?: Role[];
}

declare module "vue-router" {
  interface RouteMeta {
    title: string;
    /** 是否出现在侧栏。兜底路由与详情页为 false。 */
    nav?: boolean;
    /** 侧栏排序；路由注册顺序不保证稳定，必须显式给值。 */
    order?: number;
    /** 省略表示全部角色可访问 */
    roles?: Role[];
    /** hmi＝严格灰度纪律（检测相关屏）；business＝可用正常色彩层次 */
    discipline?: "hmi" | "business";
    tabs?: TabMeta[];
    /** 不带 tab 参数时落在哪个子页；顶栏据此显示子页名，必须与视图内默认一致 */
    defaultTab?: string;
  }
}

const ENGINEER: Role[] = ["ADMIN", "ENGINEER"];

/** 路由是导航的唯一真源：侧栏、顶栏标题、视图内 tab 条、角色可见性全部从这里派生。 */
export const routes: RouteRecordRaw[] = [
  {
    path: "/overview",
    name: "overview",
    component: Overview,
    meta: {
      title: "产线总览",
      nav: true,
      order: 2,
      roles: ENGINEER,
      discipline: "hmi",
    },
  },
  {
    path: "/workbench",
    name: "workbench",
    component: Operations,
    meta: { title: "检测工作台", nav: true, order: 1, discipline: "hmi" },
  },
  {
    path: "/inspections/:id",
    name: "inspection",
    component: InspectionDetail,
    meta: { title: "单件详情与复核", nav: false, discipline: "hmi" },
  },
  {
    path: "/records/:tab?",
    name: "records",
    component: Records,
    meta: {
      title: "检测记录",
      nav: true,
      order: 3,
      discipline: "business",
      defaultTab: "queue",
      tabs: [
        { tab: "queue", label: "待办" },
        { tab: "all", label: "全部" },
      ],
    },
  },
  {
    path: "/data/:tab?",
    name: "data",
    component: Data,
    meta: {
      title: "数据管理",
      nav: true,
      order: 4,
      discipline: "business",
      defaultTab: "samples",
      tabs: [
        { tab: "tasks", label: "采样任务" },
        { tab: "samples", label: "样本库" },
        { tab: "review", label: "样本审核" },
        { tab: "annotation", label: "标注", roles: ENGINEER },
        { tab: "datasets", label: "数据集", roles: ENGINEER },
        { tab: "quality", label: "数据质量", roles: ENGINEER },
      ],
    },
  },
  {
    path: "/models/:tab?",
    name: "models",
    component: Models,
    meta: {
      title: "训练与发布",
      nav: true,
      order: 5,
      roles: ENGINEER,
      discipline: "business",
      defaultTab: "registry",
      tabs: [
        { tab: "registry", label: "模型仓库" },
        { tab: "training", label: "训练任务" },
        { tab: "benchmarks", label: "模型评估" },
        { tab: "deployments", label: "部署管理" },
      ],
    },
  },
  {
    path: "/diagnostics/:tab?",
    name: "diagnostics",
    component: Devices,
    meta: {
      title: "设备诊断",
      nav: true,
      order: 6,
      discipline: "hmi",
      defaultTab: "registry",
      tabs: [
        { tab: "registry", label: "设备" },
        { tab: "stations", label: "工位" },
        { tab: "events", label: "设备事件" },
        { tab: "debug", label: "实时事件" },
      ],
    },
  },
  {
    path: "/system/:tab?",
    name: "system",
    component: System,
    meta: {
      title: "系统管理",
      nav: true,
      order: 7,
      roles: ENGINEER,
      discipline: "business",
      defaultTab: "health",
      tabs: [
        { tab: "health", label: "系统健康" },
        { tab: "pairing", label: "移动端配对" },
        { tab: "jobs", label: "任务队列" },
        { tab: "audit", label: "操作审计", roles: ["ADMIN"] },
      ],
    },
  },
  {
    path: "/access/:tab?",
    name: "access",
    component: Access,
    meta: {
      title: "账号与注册",
      nav: true,
      order: 8,
      roles: ["ADMIN"],
      defaultTab: "users",
      tabs: [
        { tab: "users", label: "用户管理" },
        { tab: "codes", label: "注册码管理" },
      ],
    },
  },
  {
    path: "/:pathMatch(.*)*",
    name: "notFound",
    component: NotFound,
    meta: { title: "未找到", nav: false },
  },
];

export function canAccess(
  roles: Role[] | undefined,
  role: Role | null | undefined,
): boolean {
  if (!roles?.length) return true;
  return !!role && roles.includes(role);
}

/** 登录后的落地页：管理员看总览，操作工直接进工作台。 */
export function landingFor(role: Role | null | undefined) {
  return role === "ADMIN" || role === "ENGINEER" ? "overview" : "workbench";
}

/** 侧栏项，按 order 排。 */
export const navItems = routes
  .filter((r) => r.meta?.nav && r.meta.title)
  .sort((a, b) => (a.meta?.order ?? 0) - (b.meta?.order ?? 0));
