# Design System Specification: High-Density Management

## 1. Overview & Creative North Star
This design system is built upon the Creative North Star of **"The Precision Architect."** It is designed for high-stakes ERP and sales environments where data density is a requirement, not a choice. To move beyond the "standard admin template," we employ a philosophy of **Atmospheric Depth**—using light, tone, and editorial typography to create an environment that feels expansive and professional rather than crowded and clinical.

The system breaks the rigid grid through intentional "breathing zones" and asymmetric distribution of action elements, ensuring that even the most complex data tables feel like curated reports rather than raw spreadsheets.

---

## 2. Colors & Surface Philosophy

### Tonal Hierarchy
We use a sophisticated palette to define functional zones. The **Deep Navy (`#2f3133`)** sidebar provides an authoritative anchor, while the **Vibrant Primary Blue (`#003ec7`)** acts as a surgical tool for critical interactions.

### The "No-Line" Rule
Explicitly prohibited: 1px solid borders for sectioning. Structural boundaries must be defined solely through:
1.  **Background Color Shifts:** Use `surface-container-low` (`#f3f3f6`) adjacent to `surface` (`#f9f9fc`) to imply edges.
2.  **Tonal Transitions:** A transition from `surface-container` to `surface-container-high` creates a natural shelf for headers and footers.

### Glass & Gradient Signature
To elevate the experience from "tool" to "platform," utilize **Glassmorphism** for floating utility panels (e.g., Command Palettes or floating Chat-IA buttons). Use `surface_container_lowest` with a `0.8` opacity and a `20px` backdrop-blur. 

Main CTAs should leverage a subtle linear gradient: 
*   **From:** `primary` (`#003ec7`) 
*   **To:** `primary_container` (`#0052ff`) at a 135-degree angle to provide a "jeweled" depth to primary actions.

---

## 3. Typography: Editorial Authority

We use a dual-font strategy to balance character with readability.

*   **Display & Headlines (Manrope):** Large, geometric, and authoritative. Used for page titles and high-level KPIs. The wide apertures of Manrope prevent "visual fatigue" in data-heavy views.
*   **Body & Labels (Inter):** The workhorse. Inter’s tall x-height ensures that `body-sm` (`0.75rem`) remains legible in dense data tables.

**Hierarchy Note:** Always pair a `headline-sm` title with a `label-md` uppercase sub-header. This "Large-Small" pairing creates an editorial rhythm that guides the eye through complex forms.

---

## 4. Elevation & Depth: The Layering Principle

Forget the traditional Z-axis shadow; we achieve depth through **Tonal Layering**.

*   **The Stack:** 
    *   **Base:** `background` (`#f9f9fc`)
    *   **Sectioning:** `surface-container-low` (`#f3f3f6`)
    *   **Interactive Cards:** `surface-container-lowest` (`#ffffff`)
*   **Ambient Shadows:** When a card must float (e.g., a Kanban card in the Despacho view), use an extra-diffused shadow: `0px 8px 24px rgba(26, 28, 30, 0.06)`. Note the use of the `on-surface` color for the shadow tint rather than pure black.
*   **Ghost Borders:** If a border is required for accessibility in data tables, use `outline-variant` (`#c3c5d9`) at **15% opacity**. High-contrast, opaque borders are strictly forbidden as they contribute to visual noise.

---

## 5. Components

### Buttons & Actions
*   **Primary:** Gradient fill (Primary to Primary Container), `DEFAULT` roundedness (`0.5rem`).
*   **Secondary/Action:** `surface_container_high` background with `on_secondary_container` text. This "tonal" button feels integrated into the UI.
*   **Floating Action (FAB):** Specifically for the 'Chat IA' or 'New' actions, use a `xl` (`1.5rem`) corner radius and the ambient shadow spec.

### Data Tables (The Core)
*   **Header:** `surface-container-low` background, `label-md` uppercase typography.
*   **Zebra Striping:** Use `surface-container-lowest` and `surface_container_low` for alternating rows.
*   **No Dividers:** Rows are separated by the color shift. Avoid horizontal lines.
*   **Density:** Maintain a vertical padding of `2.5` (`0.5rem`) for high-density views, expanding to `4` (`0.9rem`) for standard views.

### Input Fields & Selectors
*   **Structure:** `surface-container-lowest` fill with a `sm` (`0.25rem`) corner radius.
*   **Focus State:** A 2px `surface_tint` ring with a 4px blur. No heavy solid borders.
*   **Status Chips:** Use `tertiary_container` for warnings/pending and `primary_fixed` for active states. Chips should always use `full` (`9999px`) roundedness to contrast against the architectural squareness of the table.

---

## 6. Do's and Don'ts

### Do
*   **DO** use whitespace as a separator. If you feel the need for a line, try adding `8px` of margin instead.
*   **DO** use `secondary_container` for "Soft" highlights in the sidebar or active navigation states to maintain a calm atmosphere.
*   **DO** prioritize typographic weight over color for hierarchy. Use `bold` for names and `medium` for secondary metadata.

### Don't
*   **DON'T** use pure black (`#000000`) for text. Always use `on_surface` (`#1a1c1e`) to keep the "ink" looking premium.
*   **DON'T** mix corner radii. Stick to the `DEFAULT` (`8px`) for cards and inputs to maintain a cohesive architectural language.
*   **DON'T** use high-saturation reds for errors unless it's a critical system failure. Use `error_container` for a more "muted, professional" alert.

---

## 7. Signature Layout Patterns: The "Asymmetric Dashboard"
Instead of a centered grid, align primary data metrics to the far left and secondary utility actions (Export, Filter, View) to the far right, separated by a wide "void" of whitespace. This asymmetry signals to the user that the interface is bespoke and tailored for a professional workflow, not a generic bootstrap template.