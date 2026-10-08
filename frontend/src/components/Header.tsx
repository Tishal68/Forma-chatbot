import React, { useState, useRef, useEffect, useMemo } from "react";
import { FormaMark } from "./FormaMark";
import { createPortal } from "react-dom";
import {
  Check,
  ChevronDown,
  Eye,
  Menu,
  PanelLeft,
  Pencil,
  Search,
  Sparkles,
  X,
  Zap,
} from "lucide-react";
import { ModelDetail, ProviderInfo, FeatureCoverage } from "../types";

interface HeaderProps {
  featureCoverage?: FeatureCoverage;
  sidebar: boolean;
  onOpenSidebar: () => void;
  messagesCount: number;
  title: string;
  ready: boolean;
  provider: string;
  providers: ProviderInfo[];
  onProviderChange: (provider: string) => void;
  model: string;
  models: string[];
  modelDetails?: ModelDetail[];
  busy: boolean;
  onModelChange: (model: string) => void;
  onSelectModel?: (provider: string, model: string) => void;
  onNewChat: () => void;
  onRename?: () => void;
  theme?: string;
  onToggleTheme?: () => void;
  onExportChat?: () => void;
}

export function Header({
  featureCoverage = {},
  sidebar,
  onOpenSidebar,
  messagesCount,
  title,
  ready,
  provider,
  providers,
  onProviderChange,
  model,
  models,
  modelDetails = [],
  busy,
  onModelChange,
  onSelectModel,
  onNewChat,
  onRename,
  theme = "system",
  onToggleTheme,
  onExportChat,
}: HeaderProps) {
  const [taskFilter, setTaskFilter] = useState("");
  const [sidebarSlot, setSidebarSlot] = useState<HTMLElement | null>(null);
  useEffect(() => { setSidebarSlot(document.getElementById("sidebar-model-selector")); }, []);
  const [dropdownOpen, setDropdownOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [activeFilter, setActiveFilter] = useState<"all" | "vision" | "reasoning" | "fast" | "local">("all");
  const dropdownRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const searchInputRef = useRef<HTMLInputElement>(null);
  const displayTitle = messagesCount ? title : "Your thinking space";

  // Focus search input when dropdown opens
  useEffect(() => {
    if (dropdownOpen) {
      setTimeout(() => searchInputRef.current?.focus(), 50);
    } else {
      setSearchQuery("");
      setActiveFilter("all");
    }
  }, [dropdownOpen]);

  // Close dropdown on click outside or escape key
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setDropdownOpen(false);
      }
    }
    function handleKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape" && dropdownOpen) {
        setDropdownOpen(false);
        triggerRef.current?.focus();
      }
    }
    if (dropdownOpen) {
      document.addEventListener("mousedown", handleClickOutside);
      document.addEventListener("keydown", handleKeyDown);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleKeyDown);
    };
  }, [dropdownOpen]);

  const isAuto = provider === "auto" || model === "auto" || (!provider && !model) || model === "";
  const currentDetail = modelDetails.find((m) => m.id === model);
  const currentProvider = providers.find((p) => p.id === provider);

  // Label to show in selector button
  const activeLabel = isAuto
    ? "Auto"
    : currentDetail
      ? `${currentDetail.name}`
      : model || "Choose model";

  // Filter models inside the menu based on search and capability filters
  const filteredProviders = useMemo(() => {
    const q = searchQuery.toLowerCase().trim();
    return providers.map((p) => {
      const pModels = (p.models && p.models.length > 0)
        ? p.models
        : (provider === p.id ? modelDetails : []);

      const matchingModels = pModels.filter((m) => {
        if (taskFilter && !featureCoverage[taskFilter]?.options.some(
          (option) => option.provider === p.id && option.model === m.id)) return false;
        // Capability filter
        if (activeFilter === "vision" && !m.supports_vision) return false;
        if (activeFilter === "reasoning" && !m.supports_reasoning) return false;
        if (activeFilter === "fast" && !m.is_fast) return false;
        if (activeFilter === "local" && m.provider !== "ollama") return false;

        // Search query filter
        if (!q) return true;
        return (
          m.name.toLowerCase().includes(q) ||
          m.id.toLowerCase().includes(q) ||
          (m.description && m.description.toLowerCase().includes(q)) ||
          p.name.toLowerCase().includes(q)
        );
      });

      return {
        ...p,
        filteredModels: matchingModels,
      };
    });
  }, [providers, provider, modelDetails, searchQuery, activeFilter, taskFilter, featureCoverage]);

  const totalFilteredModels = useMemo(() => {
    return filteredProviders.reduce((acc, p) => acc + p.filteredModels.length, 0);
  }, [filteredProviders]);

  const selector = (
    <div className="unified-selector" ref={dropdownRef}>
          <button
            type="button"
            ref={triggerRef}
            className={`unified-selector-btn ${dropdownOpen ? "open" : ""}`}
            onClick={() => !busy && setDropdownOpen((prev) => !prev)}
            disabled={busy}
            aria-expanded={dropdownOpen}
            aria-label={`Select model: currently ${activeLabel}`}
            title={`Active: ${activeLabel} ${currentProvider ? `(${currentProvider.name})` : ""}`}
          >
            <span className="selected-model-name">{activeLabel}</span>
            <ChevronDown size={14} className="selector-caret" />
          </button>

          {dropdownOpen && (
            <div className="unified-menu" role="menu">
              {/* Menu Search Bar */}
              <div className="menu-search-box">
                <Search size={14} className="menu-search-icon" />
                <input
                  ref={searchInputRef}
                  type="text"
                  placeholder="Filter models or providers…"
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="menu-search-input"
                />
                {searchQuery && (
                  <button
                    type="button"
                    className="menu-search-clear"
                    onClick={() => setSearchQuery("")}
                    aria-label="Clear search"
                  >
                    <X size={12} />
                  </button>
                )}
              </div>

              {Object.keys(featureCoverage).length > 0 && (
                <div className="task-model-filter">
                  <label htmlFor="model-task">Choose by task</label>
                  <select id="model-task" value={taskFilter} onChange={(e) => {
                    setTaskFilter(e.target.value); setActiveFilter("all"); setSearchQuery("");
                  }}>
                    <option value="">All models</option>
                    {Object.entries(featureCoverage).map(([key, feature]) => (
                      <option key={key} value={key}>{feature.label} ({feature.options.length})</option>
                    ))}
                  </select>
                  {taskFilter && <p role="status">{featureCoverage[taskFilter]?.message}</p>}
                </div>
              )}
              {/* Capability Filter Chips */}
              <div className="menu-filter-chips">
                {(["all", "vision", "reasoning", "fast", "local"] as const).map((filterKey) => (
                  <button
                    key={filterKey}
                    type="button"
                    className={`filter-chip ${activeFilter === filterKey ? "active" : ""}`}
                    onClick={() => setActiveFilter(filterKey)}
                  >
                    {filterKey === "all" && "All"}
                    {filterKey === "vision" && "Vision"}
                    {filterKey === "reasoning" && "Reasoning"}
                    {filterKey === "fast" && "Fast"}
                    {filterKey === "local" && "Ollama"}
                  </button>
                ))}
              </div>

              {/* Option: Auto Smart Routing (shown when no specific search query or matching 'auto') */}
              {(!searchQuery || "auto smart routing".includes(searchQuery.toLowerCase())) && activeFilter === "all" && !taskFilter && (
                <>
                  <div
                    className={`unified-menu-item auto-item ${isAuto ? "active" : ""}`}
                    role="menuitem"
                    tabIndex={0}
                    onClick={() => {
                      if (onSelectModel) {
                        onSelectModel("auto", "auto");
                      } else {
                        onProviderChange("auto");
                        onModelChange("auto");
                      }
                      setDropdownOpen(false);
                    }}
                    onKeyDown={(e) => {
                      if (e.key === "Enter" || e.key === " ") {
                        if (onSelectModel) {
                          onSelectModel("auto", "auto");
                        } else {
                          onProviderChange("auto");
                          onModelChange("auto");
                        }
                        setDropdownOpen(false);
                      }
                    }}
                  >
                    <div className="menu-item-left">
                      <div className="menu-item-title">
                        <Sparkles size={14} style={{ color: "var(--accent)" }} />
                        <strong>Auto (Smart Routing)</strong>
                        <span className="tag-badge default-badge">Recommended</span>
                      </div>
                      <div className="menu-item-desc">
                        Intelligently chooses the best model for chat, coding, search, documents, or images.
                      </div>
                    </div>
                    {isAuto && <Check size={16} className="active-check" />}
                  </div>

                  <div className="unified-menu-divider" />
                </>
              )}

              {/* Grouped by Provider */}
              <div className="unified-menu-providers">
                {totalFilteredModels === 0 ? (
                  <div className="menu-empty-filter">
                    No models match your filter. Try another keyword.
                  </div>
                ) : (
                  filteredProviders.map((p) => {
                    if (p.filteredModels.length === 0) return null;

                    return (
                      <div key={p.id} className="provider-group">
                        <div className="provider-group-header">
                          <span>{p.name}</span>
                          {!p.working && p.status && (
                            <span className="provider-status-tag">{p.status}</span>
                          )}
                        </div>
                        <div className="provider-model-list">
                          {p.filteredModels.map((m) => {
                            const unavailable = !p.working || (m.chat_compatible === false && !m.supports_image_generation);
                            const isCurrentActive = !isAuto && provider === p.id && model === m.id;
                            return (
                              <div
                                key={m.id}
                                className={`unified-menu-item model-item ${isCurrentActive ? "active" : ""}`}
                                role="menuitem"
                                tabIndex={unavailable ? -1 : 0}
                                aria-disabled={unavailable}
                                onClick={() => {
                                  if (unavailable) return;
                                  if (onSelectModel) {
                                    onSelectModel(p.id, m.id);
                                  } else {
                                    onProviderChange(p.id);
                                    onModelChange(m.id);
                                  }
                                  setDropdownOpen(false);
                                }}
                                onKeyDown={(e) => {
                                  if (unavailable) return;
                                  if (e.key === "Enter" || e.key === " ") {
                                    if (onSelectModel) {
                                      onSelectModel(p.id, m.id);
                                    } else {
                                      onProviderChange(p.id);
                                      onModelChange(m.id);
                                    }
                                    setDropdownOpen(false);
                                  }
                                }}
                              >
                                <div className="menu-item-left">
                                  <div className="menu-item-title">
                                    <span>{m.name}</span>
                                    {m.badge && <span className="tag-badge">{m.badge}</span>}
                                    {/* Capability tags */}
                                    <div className="capability-tags">
                                      {m.supports_vision && (
                                        <span className="cap-tag vision" title="Supports image analysis">
                                          <Eye size={10} /> Vision
                                        </span>
                                      )}
                                      {m.supports_reasoning && (
                                        <span className="cap-tag reasoning" title="Specialized in deep reasoning & coding">
                                          <Sparkles size={10} /> Reasoning
                                        </span>
                                      )}
                                      {m.is_fast && (
                                        <span className="cap-tag fast" title="Ultra-low latency">
                                          <Zap size={10} /> Fast
                                        </span>
                                      )}
                                    </div>
                                  </div>
                                  {m.description && (
                                    <div className="menu-item-desc">{m.description}</div>
                                  )}
                                </div>
                                {isCurrentActive && <Check size={16} className="active-check" />}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}
        </div>
  );

  return (
    <>
    <header className="topbar">
      <div className="header-left">
        {!sidebar && (
          <button
            className="icon-button menu-toggle-btn"
            aria-label="Open sidebar"
            onClick={onOpenSidebar}
            title="Open conversations sidebar (Ctrl + Shift + O)"
          >
            <Menu size={20} className="mobile-menu-icon" />
            <PanelLeft size={18} className="desktop-menu-icon" />
          </button>
        )}
        <div className="title-group desktop-title-group">
          <span className="header-title" title={displayTitle}>
            {displayTitle}
          </span>
          {messagesCount > 0 && onRename && (
            <button
              className="icon-button rename-title-btn"
              onClick={onRename}
              aria-label="Rename conversation"
              title="Rename conversation"
              disabled={busy}
            >
              <Pencil size={13} />
            </button>
          )}
        </div>
      </div>

      <div className="mobile-header-brand" aria-hidden="true">
        <FormaMark /><span className="brand-copy"><span>forma<span className="brand-dot">.</span></span><small className="brand-tagline">Think it. Shape it.</small></span>
      </div>

      <div className="header-right">
        {/* Unified Model & Provider Selector */}
        {(!sidebar || !sidebarSlot) && selector}
      </div>
    </header>
    {sidebar && sidebarSlot && createPortal(selector, sidebarSlot)}
    </>
  );
}
