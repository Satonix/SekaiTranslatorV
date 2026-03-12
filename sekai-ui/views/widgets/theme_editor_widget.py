from __future__ import annotations

from copy import deepcopy

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QLineEdit, QComboBox, QGroupBox, QFileDialog,
    QMessageBox, QScrollArea, QSizePolicy, QFrame, QTabWidget
)

from themes.theme_manager import ThemeManager
from views.widgets.color_field import ColorField


class ThemeEditorWidget(QWidget):
    COLOR_BINDINGS = [
        ('menu_bg', 'Fundo do menu'),
        ('menu_hover', 'Hover do menu'),
        ('window_bg', 'Janela'),
        ('panel_bg', 'Painel'),
        ('text', 'Texto principal'),
        ('muted_text', 'Texto secundário'),
        ('accent', 'Destaque'),
        ('input_bg', 'Campo'),
        ('input_border', 'Borda do campo'),
        ('background_overlay_color', 'Overlay geral'),
        ('status_in_progress', 'Status: In Progress'),
        ('status_translated', 'Status: Translated'),
        ('status_reviewed', 'Status: Reviewed'),
        ('status_overlay_in_progress', 'Overlay: In Progress'),
        ('status_overlay_translated', 'Overlay: Translated'),
        ('status_overlay_reviewed', 'Overlay: Reviewed'),
    ]

    def __init__(self, parent=None):
        super().__init__(parent)
        self._loading = False
        self._selected_theme_name = ''
        self._draft_name = ''
        self._draft_base_name = ThemeManager.DEFAULT_THEME_NAME
        self._draft_tokens: dict[str, str] = {}

        root = QHBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(12)

        left = QVBoxLayout()
        root.addLayout(left, 0)
        left.addWidget(QLabel('Temas'))
        self.theme_list = QListWidget()
        self.theme_list.setMinimumWidth(220)
        left.addWidget(self.theme_list, 1)

        row = QHBoxLayout()
        self.btn_new = QPushButton('Novo')
        self.btn_duplicate = QPushButton('Duplicar')
        self.btn_delete = QPushButton('Excluir')
        row.addWidget(self.btn_new)
        row.addWidget(self.btn_duplicate)
        row.addWidget(self.btn_delete)
        left.addLayout(row)

        row2 = QHBoxLayout()
        self.btn_import = QPushButton('Importar')
        self.btn_export = QPushButton('Exportar')
        row2.addWidget(self.btn_import)
        row2.addWidget(self.btn_export)
        left.addLayout(row2)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        root.addWidget(scroll, 1)

        host = QWidget()
        scroll.setWidget(host)
        form = QVBoxLayout(host)
        form.setSpacing(12)

        meta_box = QGroupBox('Tema')
        meta_layout = QVBoxLayout(meta_box)
        meta_layout.addWidget(QLabel('Nome do tema'))
        self.name_edit = QLineEdit()
        meta_layout.addWidget(self.name_edit)
        meta_layout.addWidget(QLabel('Tema base'))
        self.base_box = QComboBox()
        self.base_box.addItems(ThemeManager.builtin_display_names())
        meta_layout.addWidget(self.base_box)
        self.info_label = QLabel()
        self.info_label.setWordWrap(True)
        self.info_label.setProperty('mutedText', True)
        meta_layout.addWidget(self.info_label)
        form.addWidget(meta_box)

        preview_box = QGroupBox('Preview local')
        preview_layout = QVBoxLayout(preview_box)
        hint = QLabel('Este preview é só desta aba. O aplicativo inteiro só muda ao clicar em Aplicar ou OK.')
        hint.setProperty('mutedText', True)
        hint.setWordWrap(True)
        preview_layout.addWidget(hint)

        self.preview_root = QFrame()
        self.preview_root.setObjectName('ThemePreviewRoot')
        self.preview_root.setFrameShape(QFrame.StyledPanel)
        self.preview_root.setAutoFillBackground(True)
        pr = QVBoxLayout(self.preview_root)
        pr.setContentsMargins(10, 10, 10, 10)
        pr.setSpacing(10)

        menus = QHBoxLayout()
        self.preview_menu_normal = QLabel('Arquivo')
        self.preview_menu_hover = QLabel('Editar (hover)')
        for lab in (self.preview_menu_normal, self.preview_menu_hover):
            lab.setAlignment(Qt.AlignCenter)
            lab.setMinimumHeight(28)
            menus.addWidget(lab)
        menus.addStretch(1)
        pr.addLayout(menus)

        overlay_row = QHBoxLayout()
        overlay_row.addWidget(QLabel('Overlay geral'))
        self.preview_overlay_chip = QLabel('Amostra')
        self.preview_overlay_chip.setAlignment(Qt.AlignCenter)
        self.preview_overlay_chip.setMinimumHeight(26)
        self.preview_overlay_chip.setMinimumWidth(120)
        overlay_row.addWidget(self.preview_overlay_chip)
        overlay_row.addStretch(1)
        pr.addLayout(overlay_row)

        self.preview_tabs = QTabWidget()
        tab_a = QWidget()
        tab_a_layout = QVBoxLayout(tab_a)
        fields = QHBoxLayout()
        self.preview_input = QLineEdit()
        self.preview_input.setPlaceholderText('Campo de texto')
        self.preview_combo = QComboBox()
        self.preview_combo.addItems(['Opção A', 'Opção B'])
        fields.addWidget(self.preview_input, 1)
        fields.addWidget(self.preview_combo)
        tab_a_layout.addLayout(fields)

        btns = QHBoxLayout()
        self.preview_btn = QPushButton('Botão')
        self.preview_btn_accent = QPushButton('Ação')
        btns.addWidget(self.preview_btn)
        btns.addWidget(self.preview_btn_accent)
        btns.addStretch(1)
        tab_a_layout.addLayout(btns)

        statuses = QHBoxLayout()
        self.preview_status_in_progress = QLabel('In Progress')
        self.preview_status_translated = QLabel('Translated')
        self.preview_status_reviewed = QLabel('Reviewed')
        for lab in (self.preview_status_in_progress, self.preview_status_translated, self.preview_status_reviewed):
            lab.setAlignment(Qt.AlignCenter)
            lab.setMinimumHeight(26)
            statuses.addWidget(lab)
        tab_a_layout.addLayout(statuses)
        tab_a_layout.addStretch(1)

        tab_b = QWidget()
        tab_b_layout = QVBoxLayout(tab_b)
        lab = QLabel('Texto secundário / descrição do tema')
        lab.setProperty('mutedText', True)
        tab_b_layout.addWidget(QLabel('Exemplo de painel'))
        tab_b_layout.addWidget(lab)
        tab_b_layout.addStretch(1)

        self.preview_tabs.addTab(tab_a, 'Geral')
        self.preview_tabs.addTab(tab_b, 'Painel')
        pr.addWidget(self.preview_tabs)
        preview_layout.addWidget(self.preview_root)
        form.addWidget(preview_box)

        colors_box = QGroupBox('Cores')
        colors_layout = QVBoxLayout(colors_box)
        self.color_fields = {}
        for key, title in self.COLOR_BINDINGS:
            field = ColorField(key, title)
            field.colorChanged.connect(self._on_color_changed)
            self.color_fields[key] = field
            colors_layout.addWidget(field)
        form.addWidget(colors_box)
        form.addStretch(1)
        host.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)

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
            for name in ThemeManager.display_names():
                item = QListWidgetItem(name)
                spec = ThemeManager.theme_spec(name)
                item.setToolTip('Tema personalizado' if spec.is_custom else 'Tema nativo')
                self.theme_list.addItem(item)
            target = ThemeManager.normalize_theme_name(current_theme_name or ThemeManager.load_saved_theme_name())
            for i in range(self.theme_list.count()):
                if self.theme_list.item(i).text() == target:
                    self.theme_list.setCurrentRow(i)
                    break
            if self.theme_list.currentRow() < 0 and self.theme_list.count() > 0:
                self.theme_list.setCurrentRow(0)
        finally:
            self._loading = False
            self._sync_buttons()
            self._refresh_preview()

    def apply_to_settings(self) -> str:
        self._save_current_theme_changes()
        theme_name = self.current_theme_name()
        ThemeManager.save_theme_name(theme_name)
        return theme_name

    def current_theme_name(self) -> str:
        return self._selected_theme_name or ThemeManager.DEFAULT_THEME_NAME

    def _sync_buttons(self) -> None:
        spec = ThemeManager.theme_spec(self.current_theme_name())
        is_custom = spec.is_custom
        self.btn_delete.setEnabled(is_custom)
        self.btn_export.setEnabled(is_custom)
        self.name_edit.setEnabled(is_custom)
        self.base_box.setEnabled(is_custom)
        for field in self.color_fields.values():
            field.setEnabled(is_custom)
        self.info_label.setText('Tema personalizado salvo no diretório do usuário.' if is_custom else 'Tema nativo. Use Duplicar para criar uma versão editável.')

    def _on_theme_selected(self, current, previous) -> None:
        if self._loading:
            return
        try:
            self._save_current_theme_changes()
        except Exception:
            pass
        self._selected_theme_name = current.text() if current else ThemeManager.DEFAULT_THEME_NAME
        self._load_selected_theme()
        self._sync_buttons()
        self._refresh_preview()

    def _load_selected_theme(self) -> None:
        spec = ThemeManager.theme_spec(self._selected_theme_name)
        self._draft_name = spec.display_name
        base = ThemeManager.theme_spec_from_id(spec.base_theme_id or spec.id)
        self._draft_base_name = base.display_name
        self._draft_tokens = deepcopy(ThemeManager.editable_tokens_for_theme(spec.display_name))
        self._loading = True
        try:
            self.name_edit.setText(self._draft_name)
            idx = self.base_box.findText(self._draft_base_name)
            self.base_box.setCurrentIndex(max(idx, 0))
            for key, field in self.color_fields.items():
                field.setColor(str(self._draft_tokens.get(key, '') or ''))
        finally:
            self._loading = False

    def _save_current_theme_changes(self) -> None:
        if not self._selected_theme_name:
            return
        spec = ThemeManager.theme_spec(self._selected_theme_name)
        if not spec.is_custom:
            return
        new_name = ThemeManager.update_custom_theme(
            existing_name=self._selected_theme_name,
            display_name=self._draft_name,
            base_theme_name=self._draft_base_name,
            tokens=self._draft_tokens,
        )
        if new_name != self._selected_theme_name:
            self._selected_theme_name = new_name
            self.reload(current_theme_name=new_name)

    def _on_name_changed(self, text: str) -> None:
        if self._loading:
            return
        self._draft_name = (text or '').strip() or 'Tema personalizado'
        self._refresh_preview()

    def _on_base_changed(self, index: int) -> None:
        if self._loading or index < 0:
            return
        self._draft_base_name = self.base_box.currentText()
        self._refresh_preview()

    def _on_color_changed(self, key: str, value: str) -> None:
        if self._loading:
            return
        self._draft_tokens[key] = value
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        try:
            self.preview_root.setStyleSheet(ThemeManager.build_preview_stylesheet(self._draft_base_name or ThemeManager.DEFAULT_THEME_NAME, self._draft_tokens))
            self.preview_root.setPalette(ThemeManager.build_preview_palette(self._draft_base_name or ThemeManager.DEFAULT_THEME_NAME))
        except Exception:
            pass
        colors = ThemeManager.preview_status_colors(self._draft_tokens)
        for label, color in [
            (self.preview_status_in_progress, colors.get('in_progress', '#d97706')),
            (self.preview_status_translated, colors.get('translated', '#22c55e')),
            (self.preview_status_reviewed, colors.get('reviewed', '#8b5cf6')),
        ]:
            label.setStyleSheet(f'border-radius: 6px; padding: 4px 8px; background: {color};')
        menu_bg = self._draft_tokens.get('menu_bg') or '#20252d'
        menu_hover = self._draft_tokens.get('menu_hover') or '#4f8cff'
        menu_text = self._draft_tokens.get('text') or '#edf2f7'
        self.preview_menu_normal.setStyleSheet(f'padding: 4px 10px; border-radius: 6px; background: {menu_bg}; color: {menu_text};')
        self.preview_menu_hover.setStyleSheet(f'padding: 4px 10px; border-radius: 6px; background: {menu_hover}; color: white;')
        accent = self._draft_tokens.get('accent') or '#4f8cff'
        self.preview_btn_accent.setStyleSheet(f'border: 1px solid {accent};')
        overlay_color = self._draft_tokens.get('background_overlay_color') or '#000000'
        self.preview_overlay_chip.setStyleSheet(
            f'border-radius: 6px; padding: 4px 8px; background: {overlay_color}; color: white; border: 1px solid rgba(255,255,255,0.18);'
        )

    def _create_theme(self) -> None:
        name = ThemeManager.create_custom_theme('Novo Tema', self.current_theme_name())
        self.reload(current_theme_name=name)

    def _duplicate_theme(self) -> None:
        name = ThemeManager.duplicate_theme(self.current_theme_name())
        self.reload(current_theme_name=name)

    def _delete_theme(self) -> None:
        spec = ThemeManager.theme_spec(self.current_theme_name())
        if not spec.is_custom:
            return
        ans = QMessageBox.question(self, 'Temas', f"Excluir o tema '{spec.display_name}'?")
        if ans != QMessageBox.Yes:
            return
        ThemeManager.delete_custom_theme(spec.display_name)
        self.reload(current_theme_name=ThemeManager.DEFAULT_THEME_NAME)

    def _import_theme(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, 'Importar tema', '', 'Tema (*.zip)')
        if not path:
            return
        name = ThemeManager.import_custom_theme(path)
        self.reload(current_theme_name=name)

    def _export_theme(self) -> None:
        spec = ThemeManager.theme_spec(self.current_theme_name())
        if not spec.is_custom:
            QMessageBox.information(self, 'Temas', 'Duplique um tema para exportá-lo.')
            return
        path, _ = QFileDialog.getSaveFileName(self, 'Exportar tema', f'{spec.id}.zip', 'Tema (*.zip)')
        if not path:
            return
        ThemeManager.export_custom_theme(spec.display_name, path)
        QMessageBox.information(self, 'Temas', 'Tema exportado com sucesso.')
