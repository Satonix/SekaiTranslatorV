from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QLabel,
    QLineEdit,
    QComboBox,
    QGroupBox,
    QFileDialog,
    QMessageBox,
    QScrollArea,
    QSizePolicy,
    QFrame,
    QTextEdit,
)

from themes.theme_manager import ThemeManager
from views.widgets.color_field import ColorField


class ThemePreviewPanel(QFrame):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ThemePreviewRoot")

        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(10)

        self.title = QLabel("Pré-visualização")
        self.title.setStyleSheet("font-weight: 700; font-size: 14px;")
        root.addWidget(self.title)

        self.menu_bar_mock = QFrame()
        self.menu_bar_mock.setObjectName("ThemePreviewMenuBar")
        menu_layout = QHBoxLayout(self.menu_bar_mock)
        menu_layout.setContentsMargins(8, 6, 8, 6)
        menu_layout.setSpacing(10)
        for text in ("Arquivo", "Editar", "Ferramentas", "Ajuda"):
            lbl = QLabel(text)
            lbl.setObjectName("ThemePreviewMenuItem")
            menu_layout.addWidget(lbl)
        menu_layout.addStretch()
        root.addWidget(self.menu_bar_mock)

        self.panel = QGroupBox("Componentes")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setSpacing(8)

        row1 = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText("Campo de texto")
        row1.addWidget(self.input)

        self.button = QPushButton("Botão")
        row1.addWidget(self.button)
        panel_layout.addLayout(row1)

        self.text = QTextEdit()
        self.text.setPlainText("Exemplo de texto\n\nPrévia local do tema.")
        self.text.setFixedHeight(90)
        panel_layout.addWidget(self.text)

        status_row = QHBoxLayout()
        self.status_in_progress = QLabel("In Progress")
        self.status_translated = QLabel("Translated")
        self.status_reviewed = QLabel("Reviewed")
        for w in (self.status_in_progress, self.status_translated, self.status_reviewed):
            w.setAlignment(Qt.AlignCenter)
            w.setMinimumHeight(28)
            w.setStyleSheet("border-radius: 6px; padding: 4px 10px;")
            status_row.addWidget(w)
        panel_layout.addLayout(status_row)

        self.overlay_sample = QLabel("Overlay geral")
        self.overlay_sample.setAlignment(Qt.AlignCenter)
        self.overlay_sample.setMinimumHeight(42)
        self.overlay_sample.setStyleSheet("border-radius: 8px;")
        panel_layout.addWidget(self.overlay_sample)

        root.addWidget(self.panel)

    def apply_preview(
        self,
        *,
        stylesheet: str,
        palette: QPalette,
        status_colors: dict[str, str],
        overlay_color: str,
    ) -> None:
        self.setPalette(palette)
        self.setAutoFillBackground(True)
        self.setStyleSheet(stylesheet)

        self._apply_status_style(self.status_in_progress, status_colors.get("in_progress", "#d97706"))
        self._apply_status_style(self.status_translated, status_colors.get("translated", "#22c55e"))
        self._apply_status_style(self.status_reviewed, status_colors.get("reviewed", "#8b5cf6"))

        color = QColor(overlay_color or "#000000")
        if not color.isValid():
            color = QColor("#000000")
        rgba = f"rgba({color.red()}, {color.green()}, {color.blue()}, 0.65)"
        self.overlay_sample.setStyleSheet(
            f"border-radius: 8px; background: {rgba}; color: white; padding: 8px;"
        )

    @staticmethod
    def _apply_status_style(widget: QLabel, color: str) -> None:
        q = QColor(color)
        if not q.isValid():
            q = QColor("#777777")
        widget.setStyleSheet(
            f"border-radius: 6px; padding: 4px 10px; "
            f"background: {q.name()}; color: white; font-weight: 600;"
        )


class ThemeEditorWidget(QWidget):
    themeApplied = Signal(str)

    COLOR_BINDINGS = [
        ("window_bg", "Janela"),
        ("panel_bg", "Painel"),
        ("text", "Texto principal"),
        ("muted_text", "Texto secundário"),
        ("accent", "Destaque"),
        ("menu_bg", "Menu"),
        ("menu_hover", "Hover do menu"),
        ("input_bg", "Campo"),
        ("input_border", "Borda do campo"),
        ("background_overlay_color", "Overlay geral"),
        ("status_in_progress", "Status: In Progress"),
        ("status_translated", "Status: Translated"),
        ("status_reviewed", "Status: Reviewed"),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._selected_theme_name = ""
        self._draft_name = ""
        self._draft_base_theme_name = ThemeManager.DEFAULT_THEME_NAME
        self._draft_tokens: dict[str, Any] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        left = QVBoxLayout()
        root.addLayout(left, 0)

        left.addWidget(QLabel("Temas"))
        self.theme_list = QListWidget()
        self.theme_list.setMinimumWidth(220)
        left.addWidget(self.theme_list, 1)

        left_buttons = QHBoxLayout()
        self.btn_new = QPushButton("Novo")
        self.btn_duplicate = QPushButton("Duplicar")
        self.btn_delete = QPushButton("Excluir")
        left_buttons.addWidget(self.btn_new)
        left_buttons.addWidget(self.btn_duplicate)
        left_buttons.addWidget(self.btn_delete)
        left.addLayout(left_buttons)

        io_buttons = QHBoxLayout()
        self.btn_import = QPushButton("Importar")
        self.btn_export = QPushButton("Exportar")
        io_buttons.addWidget(self.btn_import)
        io_buttons.addWidget(self.btn_export)
        left.addLayout(io_buttons)

        right = QVBoxLayout()
        root.addLayout(right, 1)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        right.addWidget(scroll, 1)

        form_host = QWidget()
        scroll.setWidget(form_host)
        form = QVBoxLayout(form_host)
        form.setSpacing(12)

        meta_box = QGroupBox("Tema")
        meta_layout = QVBoxLayout(meta_box)
        meta_layout.addWidget(QLabel("Nome do tema"))
        self.name_edit = QLineEdit()
        meta_layout.addWidget(self.name_edit)

        meta_layout.addWidget(QLabel("Tema base"))
        self.base_box = QComboBox()
        meta_layout.addWidget(self.base_box)

        self.info_label = QLabel()
        self.info_label.setProperty("mutedText", True)
        self.info_label.setWordWrap(True)
        meta_layout.addWidget(self.info_label)
        form.addWidget(meta_box)

        colors_box = QGroupBox("Cores")
        colors_layout = QVBoxLayout(colors_box)
        self.color_fields: dict[str, ColorField] = {}
        for key, label in self.COLOR_BINDINGS:
            field = ColorField(key, label)
            self.color_fields[key] = field
            colors_layout.addWidget(field)
            field.colorChanged.connect(self._on_color_changed)
        form.addWidget(colors_box)

        self.preview = ThemePreviewPanel()
        self.preview.setMinimumHeight(280)
        form.addWidget(self.preview)

        form.addStretch()
        form_host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

        self.theme_list.currentItemChanged.connect(self._on_theme_selected)
        self.btn_new.clicked.connect(self._create_theme)
        self.btn_duplicate.clicked.connect(self._duplicate_theme)
        self.btn_delete.clicked.connect(self._delete_theme)
        self.btn_import.clicked.connect(self._import_theme)
        self.btn_export.clicked.connect(self._export_theme)
        self.name_edit.textChanged.connect(self._on_name_changed)
        self.base_box.currentIndexChanged.connect(self._on_base_changed)

        self.reload()

    def reload(self, current_theme_name: str | None = None) -> None:
        self._loading = True
        try:
            self.theme_list.clear()
            self.base_box.clear()
            self.base_box.addItems(ThemeManager.builtin_display_names())

            for name in ThemeManager.display_names():
                item = QListWidgetItem(name)
                spec = ThemeManager.theme_spec(name)
                item.setToolTip("Tema personalizado" if spec.is_custom else "Tema nativo")
                self.theme_list.addItem(item)

            target = ThemeManager.normalize_theme_name(
                current_theme_name or ThemeManager.load_saved_theme_name()
            )
            for i in range(self.theme_list.count()):
                if self.theme_list.item(i).text() == target:
                    self.theme_list.setCurrentRow(i)
                    break

            if not self.theme_list.currentItem() and self.theme_list.count() > 0:
                self.theme_list.setCurrentRow(0)
        finally:
            self._loading = False
            self._sync_buttons()

    def current_theme_name(self) -> str:
        return self._selected_theme_name or ThemeManager.DEFAULT_THEME_NAME

    def apply_to_settings(self) -> str:
        self._save_current_theme_changes()
        name = self.current_theme_name()
        ThemeManager.save_theme_name(name)
        self.themeApplied.emit(name)
        return name

    def _sync_buttons(self) -> None:
        spec = ThemeManager.theme_spec(self._selected_theme_name)
        is_custom = spec.is_custom
        self.btn_delete.setEnabled(is_custom)
        self.btn_export.setEnabled(is_custom)
        self.name_edit.setEnabled(is_custom)
        self.base_box.setEnabled(is_custom)

        for field in self.color_fields.values():
            field.setEnabled(is_custom)

        self.info_label.setText(
            "Tema personalizado salvo em %LOCALAPPDATA%\\SekaiTranslatorV\\themes."
            if is_custom
            else "Tema nativo. Use Duplicar para criar uma versão editável."
        )

    def _on_theme_selected(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if self._loading:
            return
        try:
            self._save_current_theme_changes()
        except Exception:
            pass

        self._selected_theme_name = current.text() if current else ThemeManager.DEFAULT_THEME_NAME
        self._load_selected_theme()
        self._sync_buttons()
        self._update_preview()

    def _load_selected_theme(self) -> None:
        spec = ThemeManager.theme_spec(self._selected_theme_name)
        self._draft_name = spec.display_name
        self._draft_base_theme_name = ThemeManager.theme_spec_from_id(spec.base_theme_id or spec.id).display_name
        self._draft_tokens = ThemeManager.editable_tokens_for_theme(spec.display_name)

        self._loading = True
        try:
            self.name_edit.setText(self._draft_name)
            idx = self.base_box.findText(self._draft_base_theme_name)
            self.base_box.setCurrentIndex(max(0, idx))
            for key, field in self.color_fields.items():
                field.setColor(self._draft_tokens.get(key, ""))
        finally:
            self._loading = False

    def _save_current_theme_changes(self) -> None:
        if not self._selected_theme_name:
            return

        spec = ThemeManager.theme_spec(self._selected_theme_name)
        if not spec.is_custom:
            return

        final_name = ThemeManager.update_custom_theme(
            existing_name=self._selected_theme_name,
            display_name=self._draft_name,
            base_theme_name=self._draft_base_theme_name,
            tokens=self._draft_tokens,
        )

        if final_name != self._selected_theme_name:
            self._selected_theme_name = final_name
            self.reload(current_theme_name=final_name)

    def _on_name_changed(self, text: str) -> None:
        if self._loading:
            return
        self._draft_name = (text or "").strip() or "Tema personalizado"
        self._update_preview()

    def _on_base_changed(self, index: int) -> None:
        if self._loading or index < 0:
            return
        self._draft_base_theme_name = self.base_box.currentText() or ThemeManager.DEFAULT_THEME_NAME
        self._update_preview()

    def _on_color_changed(self, key: str, value: str) -> None:
        if self._loading:
            return
        self._draft_tokens[key] = value
        self._update_preview()

    def _update_preview(self) -> None:
        base_name = self._draft_base_theme_name or self.current_theme_name()
        stylesheet = ThemeManager.build_preview_stylesheet(base_name, self._draft_tokens)
        palette = ThemeManager.build_preview_palette(base_name)
        status_colors = ThemeManager.preview_status_colors(self._draft_tokens)
        overlay_color = str(self._draft_tokens.get("background_overlay_color") or "#000000")

        self.preview.apply_preview(
            stylesheet=stylesheet,
            palette=palette,
            status_colors=status_colors,
            overlay_color=overlay_color,
        )

    def _create_theme(self) -> None:
        new_name = ThemeManager.create_custom_theme(
            display_name="Novo Tema",
            base_theme_name=self.current_theme_name(),
        )
        self.reload(current_theme_name=new_name)

    def _duplicate_theme(self) -> None:
        new_name = ThemeManager.duplicate_theme(self.current_theme_name())
        self.reload(current_theme_name=new_name)

    def _delete_theme(self) -> None:
        spec = ThemeManager.theme_spec(self.current_theme_name())
        if not spec.is_custom:
            return

        ans = QMessageBox.question(self, "Temas", f"Excluir o tema '{spec.display_name}'?")
        if ans != QMessageBox.Yes:
            return

        ThemeManager.delete_custom_theme(spec.display_name)
        self.reload(current_theme_name=ThemeManager.DEFAULT_THEME_NAME)

    def _import_theme(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Importar tema", "", "Tema (*.zip)")
        if not path:
            return
        name = ThemeManager.import_custom_theme(path)
        self.reload(current_theme_name=name)

    def _export_theme(self) -> None:
        spec = ThemeManager.theme_spec(self.current_theme_name())
        if not spec.is_custom:
            QMessageBox.information(self, "Temas", "Duplique um tema nativo para exportá-lo.")
            return

        path, _ = QFileDialog.getSaveFileName(
            self,
            "Exportar tema",
            f"{spec.id}.zip",
            "Tema (*.zip)",
        )
        if not path:
            return

        ThemeManager.export_custom_theme(spec.display_name, path)
        QMessageBox.information(self, "Temas", "Tema exportado com sucesso.")