import type {
  UiButton,
  UiInput,
  UiSelect,
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
