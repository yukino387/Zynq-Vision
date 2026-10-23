import type { RouteRecordRaw } from "vue-router";
import type { Role } from "@vision/contracts";
import Overview from "./views/Overview.vue";
import Showcase from "./views/Showcase.vue";
import Operations from "./views/Operations.vue";
import Records from "./views/Records.vue";
import InspectionDetail from "./views/InspectionDetail.vue";
import Data from "./views/Data.vue";
import Models from "./views/Models.vue";
import Firmware from "./views/Firmware.vue";
import Devices from "./views/Devices.vue";
import System from "./views/System.vue";
import NotFound from "./views/NotFound.vue";
import Access from "./views/Access.vue";
import Plans from "./views/Plans.vue";
import Account from "./views/Account.vue";
import Production from "./views/Production.vue";

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
export const roleDuties = {
  ADMIN: {
    name: "管理工作区",
    summary: "配置方案、分配采样、审核数据、训练与批准发布",
  },
  OPERATOR: {
    name: "操作员工作区",
    summary: "按任务采样、查看结果、提交复核意见",
  },
  ENGINEER: {
    name: "技术维护区",
    summary: "维护设备、标注与训练；方案、任务管理及业务数据删除由管理员负责",
  },
};

/** 路由是导航的唯一真源：侧栏、顶栏标题、视图内 tab 条、角色可见性全部从这里派生。 */
export const routes: RouteRecordRaw[] = [
  {
    path: "/production",
    name: "production",
    component: Production,
    meta: { title: "生产批次", nav: true, order: 3.2, discipline: "hmi" },
  },
  {
    path: "/analytics",
    redirect: { path: "/production", query: { tab: "stats" } },
  },
  {
    path: "/account",
    name: "account",
    component: Account,
    meta: { title: "账号设置", nav: false, discipline: "business" },
  },
  {
    path: "/showcase",
    name: "showcase",
    component: Showcase,
    meta: { title: "演示大屏", nav: true, order: 0, discipline: "business" },
  },
  {
    path: "/overview",
    name: "overview",
    component: Overview,
    meta: {
      title: "运行概览",
      nav: true,
      order: 1,
      roles: ENGINEER,
      discipline: "business",
    },
  },
  {
    path: "/plans",
    name: "plans",
    component: Plans,
    meta: {
      title: "产品配置",
      nav: true,
      order: 2,
      roles: ENGINEER,
      discipline: "business",
    },
  },
  {
    path: "/workbench",
    name: "workbench",
    component: Operations,
    meta: { title: "现场工作台", nav: true, order: 3, discipline: "hmi" },
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
      order: 4,
      discipline: "business",
      defaultTab: "all",
      tabs: [
        { tab: "all", label: "全部记录" },
        { tab: "uncertain", label: "判定不确定" },
        { tab: "errors", label: "检测错误" },
      ],
    },
  },
  {
    path: "/data/:tab?",
    name: "data",
    component: Data,
    meta: {
      title: "样本管理",
      nav: true,
      order: 5,
      roles: ENGINEER,
      discipline: "business",
      defaultTab: "annotation",
      tabs: [
        { tab: "samples", label: "样本库" },
        { tab: "annotation", label: "标注与筛选", roles: ENGINEER },
        { tab: "datasets", label: "训练快照", roles: ENGINEER },
      ],
    },
  },
  {
    path: "/models/:tab?",
    name: "models",
    component: Models,
    meta: {
      title: "模型与发布",
      nav: true,
      order: 6,
      roles: ENGINEER,
      discipline: "business",
      defaultTab: "registry",
      tabs: [
        { tab: "registry", label: "模型仓库" },
        { tab: "training", label: "训练任务" },
        { tab: "deployments", label: "开始检测", roles: ENGINEER },
      ],
    },
  },
  {
    path: "/firmware/:tab?",
    name: "firmware",
    component: Firmware,
    meta: {
      title: "终端与更新",
      nav: false,
      order: 7,
      roles: ENGINEER,
      discipline: "business",
      defaultTab: "overview",
      tabs: [
        { tab: "overview", label: "更新能力" },
        { tab: "registry", label: "旧固件档案" },
        { tab: "deployments", label: "历史发布记录" },
      ],
    },
  },
  {
    path: "/diagnostics/:tab?",
    name: "diagnostics",
    component: Devices,
    meta: {
      title: "设备诊断",
      roles: ENGINEER,
      nav: true,
      order: 8,
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
      order: 9,
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
      title: "人员与权限",
      nav: true,
      order: 10,
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

/** 登录后的落地页：管理员看总览，操作工直接进板端检测作业。 */
export function landingFor(_role: Role | null | undefined) {
  return "workbench";
}

/** 侧栏项，按 order 排。 */
export const navItems = routes
  .filter((r) => r.meta?.nav && r.meta.title)
  .sort((a, b) => (a.meta?.order ?? 0) - (b.meta?.order ?? 0));
