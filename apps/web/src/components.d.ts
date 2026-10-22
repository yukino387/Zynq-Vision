import type {
  UiButton,
  UiInput,
  UiSelect,
  UiSwitch,
  UiAlert,
  UiProgress,
  UiCard,
  UiBadge,
  UiModal,
  UiTabs,
  UiStat,
  UiEmpty,
  UiTable,
  UiThemeToggle,
} from "./components/ui";

declare module "@vue/runtime-core" {
  export interface GlobalComponents {
    UiButton: typeof UiButton;
    UiInput: typeof UiInput;
    UiSelect: typeof UiSelect;
    UiSwitch: typeof UiSwitch;
    UiAlert: typeof UiAlert;
    UiProgress: typeof UiProgress;
    UiCard: typeof UiCard;
    UiBadge: typeof UiBadge;
    UiModal: typeof UiModal;
    UiTabs: typeof UiTabs;
    UiStat: typeof UiStat;
    UiEmpty: typeof UiEmpty;
    UiTable: typeof UiTable;
    UiThemeToggle: typeof UiThemeToggle;
  }
}

export {};
