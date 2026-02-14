from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QRadioButton,
    QGroupBox,
    QMessageBox,
)


class QADialog(QDialog):
    """
    Dialog simples de QA (Quality Assurance) — placeholder.
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("QA - Verificação de Qualidade")
        self.resize(520, 380)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        # Título
        title = QLabel("Verificação de Qualidade (QA)")
        title.setStyleSheet("font-size: 14px; font-weight: bold;")
        layout.addWidget(title)

        # Escopo
        scope_box = QGroupBox("Escopo")
        scope_layout = QVBoxLayout(scope_box)

        self.radio_file = QRadioButton("Arquivo atual")
        self.radio_project = QRadioButton("Projeto inteiro")
        self.radio_file.setChecked(True)

        scope_layout.addWidget(self.radio_file)
        scope_layout.addWidget(self.radio_project)

        layout.addWidget(scope_box)

        # Resultados
        results_label = QLabel("Resultados:")
        layout.addWidget(results_label)

        self.results_list = QListWidget()
        layout.addWidget(self.results_list, 1)

        # Dados fake
        self._load_dummy_results()

        # Botões
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.btn_run = QPushButton("Executar QA")
        self.btn_close = QPushButton("Fechar")

        btn_layout.addWidget(self.btn_run)
        btn_layout.addWidget(self.btn_close)

        layout.addLayout(btn_layout)

        # Conexões
        self.btn_close.clicked.connect(self.reject)
        self.btn_run.clicked.connect(self._run_qa)

    # Internals
    def _load_dummy_results(self):
        """
        Resultados fictícios para UX.
        """
        issues = [
            "[Aviso] Linha 23: possível overflow",
            "[Erro] Linha 45: tag não fechada",
            "[Aviso] Linha 78: texto muito longo",
        ]
        self.results_list.addItems(issues)

    def _run_qa(self):
        QMessageBox.information(
            self,
            "QA",
            "Execução de QA ainda não implementada."
        )
