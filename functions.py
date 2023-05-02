from classes import Point3D
import math
import numpy as np


def create_mesh(width: int, height: int) -> np.ndarray[Point3D]:
    return np.array(list([[Point3D(x, y, 0, x, y) for x in range(width)] for y in range(height)]))


def triangle_area(p1, p2, p3):
    dist = lambda pt1, pt2: math.sqrt((pt2.x - pt1.x)**2 + (pt2.y - pt1.y)**2)
    A = dist(p1, p2)
    B = dist(p2, p3)
    C = dist(p3, p1)
    s = (A + B + C) / 2
    return math.sqrt(s * (s - A) * (s - B) * (s - C))


def compute_pixel_area(points: np.ndarray[Point3D]) -> np.ndarray[float]:
    height, width = points.shape
    pixel_area = np.empty((height - 1, width - 1))

    for y in range(height - 1):
        for x in range(width - 1):
            ul = points[y, x]
            ur = points[y, x + 1]
            ll = points[y + 1, x]
            lr = points[y + 1, x + 1]
            pixel_area[y, x] = triangle_area(ul, ur, ll) + triangle_area(ur, ll, lr)

    return pixel_area 


def compute_loss(mesh: np.ndarray[Point3D], img: np.ndarray) -> np.ndarray:
    D = compute_pixel_area(mesh) - img
    D -= D.sum() / (img.shape[0] * img.shape[1])  
    return D


def grad(f: np.ndarray[float]):
    u, v = np.empty_like(f), np.empty_like(f)
    u[:, -1], v[-1, :] = 0, 0
    np.subtract(f[:, 1:], f[:, :-1], out=u[:, :-1])
    np.subtract(f[1:, :], f[:-1, :], out=v[:-1, :])
    return u, v


def calculate_t(p1: Point3D, p2: Point3D, p3: Point3D, dp1: Point3D, dp2: Point3D, dp3: Point3D):
    x1 = p2.x - p1.x
    y1 = p2.y - p1.y

    x2 = p3.x - p1.x
    y2 = p3.y - p1.y

    u1 = dp2.x - dp1.x
    v1 = dp2.y - dp1.y

    u2 = dp3.x - dp1.x
    v2 = dp3.y - dp1.y

    a = u1 * v2 - u2 * v1
    b = x1 * v1 + y2 * u1 - x2 * v1 - y1 * u2
    c = x1 * y2 - x2 * y1

    if a != 0:
        q = b ** 2 - 4 * a * c
        if q >= 0:
            d = math.sqrt(q)
            return (-b - d) / (2 * a), (-b + d) / (2 * a)
        else:
            return -123.0, -123.0
    return -c / b , -c / b


def step_mesh(points: np.ndarray[Point3D], phi: np.ndarray[float]):
    phi_u, phi_v = grad(phi)
    h, w = points.shape
    velocities = np.empty(points.shape, dtype=Point3D)
    for y in range(h):
        for x in range(w):
            if x == w - 1:
                u = 0.0
            else:
                u = phi_u[y - 1, x] if y == h - 1 else phi_u[y, x]
            
            if y == h - 1:
                v = 0.0
            else:
                v = phi_v[y, x - 1] if x == w - 1 else phi_v[y, x]
            
            velocities[y, x] = Point3D(-u, -v, 0, 0, 0)
    
    min_t = 10000
    triangle_count = 1
    for y in range(h - 1):
        for x in range(w - 1):
            tr1 = (points[y, x], points[y, x + 1], points[y + 1, x])
            tr2 = (points[y, x + 1], points[y + 1, x], points[y + 1, x + 1])

            for p1, p2, p3 in [tr1, tr2]:
                v1, v2, v3 = velocities[p1.iy, p1.ix], velocities[p2.iy, p2.ix], velocities[p3.iy, p3.ix]
                t1, t2 = calculate_t(p1, p2, p3, v1, v2, v3)
                if 0 < t1 < min_t:
                    min_t = t1
                if 0 < t2 < min_t:
                    min_t = t2
                triangle_count += 1
    
    print("Overall min_t", min_t)
    
    coeff = min_t / 2
    for y in range(h):
        for x in range(w):
            p = points[y, x]
            v = velocities[p.iy, p.ix]
            points[y, x].x = v.x * coeff + p.x
            points[y, x].y = v.y * coeff + p.y


def solidify(input_mesh: np.ndarray[Point3D], offset=100) -> np.ndarray[Point3D]:
    height, width = input_mesh.shape[:2]
    total_nodes = width * height * 2

    node_list = np.empty(total_nodes, dtype=Point3D)
    node_array_top = np.empty((height, width), dtype=Point3D)
    node_array_bottom = np.empty((height, width), dtype=Point3D)

    num_edge_nodes = width * 2 + (height - 2) * 2

    num_triangles_top = (width - 1) * (height - 1) * 2
    num_triangles_bottom = num_triangles_top
    num_triangles_edges = num_edge_nodes * 2

    total_triangles = num_triangles_bottom + num_triangles_top + num_triangles_edges

    print(f"Specs: {width}  {height}  {total_nodes}  {num_edge_nodes}  {num_triangles_bottom} {total_triangles}")

    # Build the bottom surface
    count = 0
    for y in range(height):
        for x in range(width):
            new_point = Point3D(x, y, -offset, x, y)
            node_list[count] = new_point
            node_array_bottom[y, x] = new_point
            count += 1

    # Copy in the top surface
    for y in range(height):
        for x in range(width):
            node = input_mesh[y, x] # Point3D object
            if node.ix != x:
                print(f"OH NO POINTS NOT MATCHED {x} vs {node.ix}")
            if node.iy != y:
                print(f"OH NO POINTS NOT MATCHED {y} vs {node.iy}")

            node_list[count] = node
            node_array_top[y, x] = node
            count += 1
    
    print(f"We now have {count - 1} valid nodes")

    triangles = np.empty(shape=(total_triangles, 3))
    # Build the triangles for the bottom surface
    count = 0
    for y in range(height - 1):
        for x in range(width - 1):
            # here x and y establish the column of squares we're in
            index_ul = (y - 1) * width + x
            index_ur = index_ul + 1

            index_ll = y * width + x
            index_lr = index_ll + 1

            triangles[count][0] = index_ul
            triangles[count][1] = index_ll
            triangles[count][2] = index_ur
            count += 1

            triangles[count][0] = index_lr
            triangles[count][1] = index_ur
            triangles[count][2] = index_ll
            count += 1
    
    print(triangles)

    print(f"We've filled up {count - 1} triangles")

    # Build the triangles to close the mesh

    x = 1
    for y in range(height - 1):
        ll = (y - 1) * width + x
        ul = ll + total_nodes / 2
        lr = y * width + x
        ur = lr + total_nodes / 2
        
        triangles[count][0] = ll
        triangles[count][1] = ul
        triangles[count][2] = ur
        count += 1
        
        triangles[count][0] = ur
        triangles[count][1] = lr
        triangles[count][2] = ll
        count += 1

    x = width
    for y in range(height - 1):
        ll = (y - 1) * width + x
        ul = ll + total_nodes / 2
        lr = y * width + x
        ur = lr + total_nodes / 2
        
        triangles[count][0] = ll
        triangles[count][1] = ur
        triangles[count][2] = ul
        count += 1
        
        triangles[count][0] = ur
        triangles[count][1] = ll
        triangles[count][2] = lr
        count += 1

    y = 1
    for x in range(1, width):
        ll = (y - 1) * width + x
        ul = ll + total_nodes / 2
        lr = (y - 1) * width + (x - 1)
        ur = lr + total_nodes / 2
        
        triangles[count][0] = ll
        triangles[count][1] = ul
        triangles[count][2] = ur
        count += 1
        
        triangles[count][0] = ur
        triangles[count][1] = lr
        triangles[count][2] = ll
        count += 1

    y = height
    for x in range(1, width):
        ll = (y - 1) * width + x
        ul = ll + total_nodes / 2
        lr = (y - 1) * width + (x - 1)
        ur = lr + total_nodes / 2
        
        triangles[count][0] = ll
        triangles[count][1] = ur
        triangles[count][2] = ul
        count += 1
        
        triangles[count][0] = ur
        triangles[count][1] = ll
        triangles[count][2] = lr
        count += 1

    return node_list, node_array_bottom, triangles, width, height