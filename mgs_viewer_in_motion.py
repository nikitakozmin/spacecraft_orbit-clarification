import sys
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget
from PyQt5.QtCore import QTimer
from PyQt5.QtGui import QSurfaceFormat
from OpenGL.GL import *
from OpenGL.GLU import *


# ============================================================
# КОНФИГ ВИЗУАЛИЗАЦИИ
# ============================================================

CONFIG = {
    # ---- ВРЕМЯ ----
    # 1.0  = реальное время (1 кадр = 1 измерение)
    # 10.0 = в 10 раз быстрее реального
    # 0.1  = замедление в 10 раз
    "time_speed": 5.0,

    # ---- МАСШТАБЫ ----
    # Марс в реальном масштабе (км)
    "mars_radius_km": 3390,

    # Атмосфера
    "atmosphere_scale": 1.07,  # 7% выше радиуса Марса
    "atmosphere_alpha": 0.12,

    # Космический аппарат (искусственно увеличен)
    "spacecraft_scale": 150,   # км (визуальный коэффициент)

    # ---- СОЛНЕЧНАЯ СИСТЕМА ----
    "sun_radius_km": 696_000,  # сильно уменьшено, иначе гигант
    "sun_distance_scale": 1.0,       # 1.0 = реальные расстояния

    # ---- КАМЕРА ----
    "min_zoom": 5_000,
    "max_zoom": 5e10,  # ~5 млрд км (уровень Солнечной системы)
    "zoom_sensitivity": 0.002,
}


# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================

def load_geometry_data(path):
    df = pd.read_csv(path)

    xyz = df[['mgs_x_km', 'mgs_y_km', 'mgs_z_km']].to_numpy()
    mars_sun = df[['mars_sun_x_km', 'mars_sun_y_km', 'mars_sun_z_km']].iloc[0].to_numpy()

    return xyz, mars_sun


# ============================================================
# OPENGL ВИДЖЕТ
# ============================================================

class OrbitViewer(QOpenGLWidget):

    def __init__(self, xyz, mars_sun):
        super().__init__()
        self.xyz = xyz
        self.mars_sun = mars_sun
        self.index = 0

        # Камера
        self.rot_x = -40
        self.rot_y = 30
        self.zoom = 35000

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_animation)
        self.timer.start(30)

        self.setFocusPolicy(True)

    # -------------------
    # INIT
    # -------------------

    def initializeGL(self):
        glClearColor(0.01, 0.01, 0.03, 1.0)

        glEnable(GL_DEPTH_TEST)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)

        glEnable(GL_LINE_SMOOTH)
        glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)

        self.quad = gluNewQuadric()

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(
            45,
            w / h if h else 1,
            1000,      # near = 1000 км
            1e10        # far = 10 млрд км
        )
        glMatrixMode(GL_MODELVIEW)

    # -------------------
    # RENDER
    # -------------------

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()

        glTranslatef(0, 0, -self.zoom)
        glRotatef(self.rot_x, 1, 0, 0)
        glRotatef(self.rot_y, 0, 1, 0)

        self.draw_sun()
        self.draw_mars_wireframe()
        self.draw_mars_atmosphere()
        self.draw_trajectory()
        self.draw_spacecraft()

    # ===========================================================
    # OBJECTS
    # ===========================================================

    def draw_sun(self):
        glPushMatrix()

        sun_pos = -self.mars_sun * CONFIG["sun_distance_scale"]

        glTranslatef(*sun_pos)
        glColor3f(1.0, 0.75, 0.2)

        gluQuadricDrawStyle(self.quad, GLU_LINE)
        glLineWidth(1.5)

        gluSphere(
            self.quad,
            CONFIG["sun_radius_km"],
            48, 48   # больше сегментов — красивее каркас
        )

        glPopMatrix()

    def draw_mars_wireframe(self):
        glPushMatrix()
        glColor3f(0.9, 0.3, 0.3)
        gluQuadricDrawStyle(self.quad, GLU_LINE)
        gluSphere(
            self.quad,
            CONFIG["mars_radius_km"],
            36,
            36
        )
        glPopMatrix()
    
    def draw_mars_atmosphere(self):
        glPushMatrix()
        glColor4f(0.4, 0.6, 1.0, CONFIG["atmosphere_alpha"])
        gluQuadricDrawStyle(self.quad, GLU_FILL)
        gluSphere(
            self.quad,
            CONFIG["mars_radius_km"] * CONFIG["atmosphere_scale"],
            36,
            36
        )
        glPopMatrix()

    def draw_trajectory(self):
        glColor3f(0.3, 0.8, 1.0)
        glBegin(GL_LINE_STRIP)
        for x, y, z in self.xyz:
            glVertex3f(x, y, z)
        glEnd()

    def draw_spacecraft(self):
        x, y, z = self.xyz[self.index]

        glPushMatrix()
        glTranslatef(x, y, z)
        glColor3f(1.0, 1.0, 0.3)

        gluQuadricDrawStyle(self.quad, GLU_FILL)
        gluSphere(
            self.quad,
            CONFIG["spacecraft_scale"],
            16,
            16
        )

        glPopMatrix()
    
    # ===========================================================
    # ANIMATION
    # ===========================================================

    def update_animation(self):
        self.index += CONFIG["time_speed"]
        self.index %= len(self.xyz)
        self.index = int(self.index)
        self.update()

    # ===========================================================
    # CAMERA CONTROL
    # ===========================================================

    def wheelEvent(self, event):
        delta = event.angleDelta().y()

        # линейный шаг зума (км за один "щелчок")
        zoom_step = 2000

        self.zoom -= delta / 120 * zoom_step

        self.zoom = max(CONFIG["min_zoom"], min(self.zoom, CONFIG["max_zoom"]))
        self.update()

    def mousePressEvent(self, event):
        self.last_mouse = (event.x(), event.y())

    def mouseMoveEvent(self, event):
        dx = event.x() - self.last_mouse[0]
        dy = event.y() - self.last_mouse[1]
        self.last_mouse = (event.x(), event.y())

        self.rot_x += dy * 0.4
        self.rot_y += dx * 0.4
        self.update()


# ============================================================
# MAIN WINDOW
# ============================================================

class MainWindow(QMainWindow):

    def __init__(self, xyz, mars_sun):
        super().__init__()
        self.setWindowTitle("Mars Global Surveyor — 3D Orbit Viewer")
        self.viewer = OrbitViewer(xyz, mars_sun)
        self.setCentralWidget(self.viewer)
        self.resize(1200, 800)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    # xyz, mars_sun = load_geometry_data("./output_data/mgs_geometry.csv")
    xyz, mars_sun = load_geometry_data("./output_data/doppler_results_integrated.csv")

    app = QApplication(sys.argv)
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)

    window = MainWindow(xyz, mars_sun)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
