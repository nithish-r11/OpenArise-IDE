from PyQt6.QtWidgets import QSplashScreen
from PyQt6.QtGui import QPixmap, QPainter, QColor, QFont, QPen
from PyQt6.QtCore import Qt, QRect

class SplashScreen(QSplashScreen):
    """
    Startup Splash Screen for OpenArise IDE.
    Clean dark card displaying title, subtitle, and loading status indicator.
    (Logo is not displayed on the splash screen per branding specification).
    """
    def __init__(self, parent=None):
        splash_width = 460
        splash_height = 510
        pixmap = QPixmap(splash_width, splash_height)
        pixmap.fill(QColor("#0a0b0e"))

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Premium subtle border
        painter.setPen(QPen(QColor("#242832"), 1.5))
        painter.drawRect(0, 0, splash_width - 1, splash_height - 1)

        # Title: OpenArise IDE
        painter.setPen(QColor("#ffffff"))
        title_font = QFont("Segoe UI", 26, QFont.Weight.Bold)
        painter.setFont(title_font)
        title_rect = QRect(0, 180, splash_width, 44)
        painter.drawText(title_rect, Qt.AlignmentFlag.AlignCenter, "OpenArise IDE")

        # Subtitle: AI-Native Coding IDE
        painter.setPen(QColor("#8ab4f8"))
        sub_font = QFont("Segoe UI", 12)
        painter.setFont(sub_font)
        sub_rect = QRect(0, title_rect.bottom() + 10, splash_width, 26)
        painter.drawText(sub_rect, Qt.AlignmentFlag.AlignCenter, "AI-Native Coding IDE")

        # Loading status indicator
        painter.setPen(QColor("#636b7b"))
        load_font = QFont("Segoe UI", 10)
        painter.setFont(load_font)
        load_rect = QRect(0, sub_rect.bottom() + 45, splash_width, 24)
        painter.drawText(load_rect, Qt.AlignmentFlag.AlignCenter, "Initializing environment and local models…")

        painter.end()

        super().__init__(pixmap, Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.SplashScreen)

