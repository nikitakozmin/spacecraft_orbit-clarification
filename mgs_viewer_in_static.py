import sys
import numpy as np
import pandas as pd
from PyQt5.QtWidgets import QApplication, QMainWindow, QOpenGLWidget
from PyQt5.QtGui import QSurfaceFormat
from OpenGL.GL import *
from OpenGL.GLU import *


# ============================================================
# КОНФИГ ВИЗУАЛИЗАЦИИ
# ============================================================

CONFIG = {
    # ---- МАСШТАБЫ ----
    "mars_radius_km": 3390,

    # Атмосфера Марса
    "atmosphere_scale": 1.07,
    "atmosphere_alpha": 0.12,

    # ---- КОСМИЧЕСКИЙ АППАРАТ ----
    "spacecraft_point_size": 4.0,

    # ---- ВЕКТОРЫ СКОРОСТИ ----
    "velocity_scale": 3000,     # км визуализации на 1 км/с
    "velocity_stride": 10,      # рисовать каждый N-й вектор

    # ---- СОЛНЕЧНАЯ СИСТЕМА ----
    "sun_radius_km": 696_000,
    "sun_distance_scale": 1.0,

    # ---- КАМЕРА ----
    "min_zoom": 5_000,
    "max_zoom": 5e10,
}


# ============================================================
# ЗАГРУЗКА ДАННЫХ
# ============================================================

def load_geometry_data(path):
    df = pd.read_csv(path)

    pos = df[['mgs_x_km', 'mgs_y_km', 'mgs_z_km']].to_numpy()
    vel = df[['mgs_vx_km_s', 'mgs_vy_km_s', 'mgs_vz_km_s']].to_numpy()

    mars_sun = df[['mars_sun_x_km', 'mars_sun_y_km', 'mars_sun_z_km']].iloc[0].to_numpy()

    return pos, vel, mars_sun


# ============================================================
# OPENGL ВИДЖЕТ
# ============================================================

class OrbitViewer(QOpenGLWidget):

    def __init__(self, pos, vel, mars_sun):
        super().__init__()
        self.pos = pos
        self.vel = vel
        self.mars_sun = mars_sun

        # Камера
        self.rot_x = -40
        self.rot_y = 30
        self.zoom = 35000

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
            1000,
            1e10
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
        self.draw_spacecraft_points()
        self.draw_velocity_vectors()

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
        gluSphere(self.quad, CONFIG["sun_radius_km"], 48, 48)

        glPopMatrix()

    def draw_mars_wireframe(self):
        glPushMatrix()
        glColor3f(0.9, 0.3, 0.3)
        gluQuadricDrawStyle(self.quad, GLU_LINE)
        gluSphere(self.quad, CONFIG["mars_radius_km"], 36, 36)
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

    def draw_spacecraft_points(self):
        glColor3f(1.0, 1.0, 0.3)
        glPointSize(CONFIG["spacecraft_point_size"])

        glBegin(GL_POINTS)
        for x, y, z in self.pos:
            glVertex3f(x, y, z)
        glEnd()

    def draw_velocity_vectors(self):
        glColor3f(0.3, 1.0, 0.3)
        glLineWidth(1.5)

        glBegin(GL_LINES)
        for i in range(0, len(self.pos), CONFIG["velocity_stride"]):
            x, y, z = self.pos[i]
            vx, vy, vz = self.vel[i]

            glVertex3f(x, y, z)
            glVertex3f(
                x + vx * CONFIG["velocity_scale"],
                y + vy * CONFIG["velocity_scale"],
                z + vz * CONFIG["velocity_scale"]
            )
        glEnd()

    # ===========================================================
    # CAMERA CONTROL
    # ===========================================================

    def wheelEvent(self, event):
        delta = event.angleDelta().y()
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

    def __init__(self, pos, vel, mars_sun):
        super().__init__()
        self.setWindowTitle("MGS — Velocity Vector Field")
        self.viewer = OrbitViewer(pos, vel, mars_sun)
        self.setCentralWidget(self.viewer)
        self.resize(1200, 800)


# ============================================================
# ENTRY POINT
# ============================================================

def main():
    pos, vel, mars_sun = load_geometry_data("./output_data/mgs_geometry.csv")

    app = QApplication(sys.argv)
    fmt = QSurfaceFormat()
    fmt.setDepthBufferSize(24)
    QSurfaceFormat.setDefaultFormat(fmt)

    window = MainWindow(pos, vel, mars_sun)
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()
