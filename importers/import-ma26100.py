#!/usr/bin/env python3
"""Import MA 26100 (Multivariate Calculus) course material into Intellect.

Why this exists: MA 26100 had an evening exam two weeks out and exactly one
2 KB material — a quiz-prep note covering section 15.2 only. Every question in
the course came from that single note, so the path showed one unit for a
four-credit course.

Sourcing note, and the honest limitation. Purdue publishes no public
lesson-by-lesson page for the current term; the Math department course page
carries no schedule and the section material is behind Brightspace. The scope
here is the **official Purdue catalog description**, retrieved from
Self-Service:

    https://selfservice.mypurdue.purdue.edu/prod/bwckctlg.p_display_courses
    ?term_in=202710&one_subj=MA&sel_crse_strt=26100&sel_crse_end=26100

    "Planes, lines, and curves in three dimensions. Differential calculus of
     several variables; multiple integrals. Introduction to vector calculus."

Unit order follows the standard Stewart chapter sequence (12-16) that MA 261
uses, which is also the order the existing 15.2 note sits in: it belongs to
the partial-derivatives unit here.

**This is scaffolding, not a substitute for the real lecture notes.** The
existing 15.2 quiz note is more specific than anything here and should keep
winning where the two overlap.
"""

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:4173/api/materials"
COURSE = "MA 26100"

CATALOG = (
    "Planes, lines, and curves in three dimensions. Differential calculus of "
    "several variables; multiple integrals. Introduction to vector calculus."
)

HEADER = f"""# MA 26100 — Multivariate Calculus

Scope from the official Purdue catalog description:

> {CATALOG}

"""

UNITS: list[tuple[str, str]] = [
    (
        "Vectors and the Geometry of Space",
        r"""
## Vectors

A vector has magnitude and direction; a point has position only. The vector
from point P to point Q is Q - P, computed componentwise. The magnitude of
\(\vec{v} = \langle a,b,c\rangle\) is \(\|\vec{v}\| = \sqrt{a^2+b^2+c^2}\), and
a unit vector in the same direction is \(\vec{v}/\|\vec{v}\|\), which is
undefined for the zero vector because it has no direction.

## The dot product

\(\vec{u}\cdot\vec{v} = u_1v_1+u_2v_2+u_3v_3 = \|\vec u\|\,\|\vec v\|\cos\theta\).
It returns a scalar. Its sign alone tells the angle's character: positive means
acute, zero means perpendicular, negative means obtuse. Two nonzero vectors are
orthogonal exactly when their dot product is zero.

The scalar projection of \(\vec u\) onto \(\vec v\) is
\(\vec u\cdot\vec v/\|\vec v\|\), and the vector projection is
\(\left(\vec u\cdot\vec v/\|\vec v\|^2\right)\vec v\). The denominators differ,
which is the usual place to slip.

## The cross product

\(\vec u\times\vec v\) returns a vector orthogonal to both, with direction
given by the right-hand rule and magnitude
\(\|\vec u\|\,\|\vec v\|\sin\theta\). It is anticommutative:
\(\vec u\times\vec v = -(\vec v\times\vec u)\). It is defined only in three
dimensions.

The magnitude of the cross product is the area of the parallelogram spanned by
the two vectors, so half of it is the area of the triangle. Two vectors are
parallel exactly when their cross product is the zero vector. The scalar triple
product \(\vec u\cdot(\vec v\times\vec w)\) gives the signed volume of the
parallelepiped, and it is zero exactly when the three vectors are coplanar.

## Lines and planes

A line through \(P_0\) with direction \(\vec v\) has vector equation
\(\vec r(t) = \vec r_0 + t\vec v\). A plane through \(P_0\) with normal
\(\vec n = \langle a,b,c\rangle\) satisfies \(\vec n\cdot(\vec r-\vec r_0)=0\),
which expands to \(a(x-x_0)+b(y-y_0)+c(z-z_0)=0\).

The coefficients of \(x\), \(y\), and \(z\) in a plane's equation are exactly
the components of a normal vector, which is what makes reading a normal off an
equation immediate. Two planes are parallel when their normals are parallel,
and the angle between two planes is the angle between their normals.

Lines in space need not intersect and need not be parallel; skew lines do
neither, which has no two-dimensional analogue.

The distance from a point to a plane is
\(|\vec n\cdot(\vec r-\vec r_0)|/\|\vec n\|\): project the offset onto the unit
normal.
""",
    ),
    (
        "Vector Functions and Curves in Space",
        r"""
## Vector-valued functions

A vector function \(\vec r(t) = \langle x(t), y(t), z(t)\rangle\) traces a curve
as \(t\) varies. Limits, derivatives, and integrals are taken componentwise, so
each component is an ordinary single-variable problem.

## Tangents and motion

\(\vec r'(t)\) is tangent to the curve and points in the direction of increasing
\(t\). In a motion interpretation \(\vec r'\) is velocity, \(\|\vec r'\|\) is
speed, and \(\vec r''\) is acceleration. The unit tangent is
\(\vec T = \vec r'/\|\vec r'\|\).

Speed is the magnitude of velocity, so it is a scalar and never negative. A
particle can have nonzero acceleration while its speed stays constant, as in
uniform circular motion, because acceleration also changes direction.

## Arc length and curvature

Arc length is \(\int_a^b \|\vec r'(t)\|\,dt\): the speed integrated over time.
Parameterizing by arc length makes the tangent a unit vector automatically.

Curvature \(\kappa = \|d\vec T/ds\|\) measures how fast the direction turns per
unit length, so it is a property of the curve rather than of the
parameterization. For a line it is zero; for a circle of radius \(a\) it is the
constant \(1/a\), so a tighter circle has larger curvature. In practice
\(\kappa = \|\vec r'\times\vec r''\|/\|\vec r'\|^3\).

Acceleration decomposes into a tangential component \(d^2s/dt^2\), which changes
speed, and a normal component \(\kappa (ds/dt)^2\), which changes direction.
There is no binormal component, which is why acceleration always lies in the
osculating plane.
""",
    ),
    (
        "Partial Derivatives, Limits, and Continuity",
        r"""
## Functions of several variables

\(f(x,y)\) assigns a number to each point of a planar domain. Its graph is a
surface in three dimensions, and a level curve \(f(x,y)=k\) is the set of points
sharing one output value. Level curves crowd together where the surface is
steep.

## Limits

\(\lim_{(x,y)\to(a,b)} f(x,y) = L\) requires the same limit along every possible
path of approach, not merely along the axes. This is the essential difference
from one variable, where only two directions exist.

The two-path test can prove a limit does not exist — find two paths giving
different values — but it can never prove one does, because no finite set of
paths exhausts the infinitely many. Approaching along \(y=mx\) and obtaining an
answer that still contains \(m\) shows the limit depends on direction and
therefore fails to exist.

Polar coordinates help when the result can be bounded independently of
\(\theta\): if \(|f| \le g(r)\) and \(g(r)\to 0\), the squeeze theorem applies.

## Continuity

\(f\) is continuous at \((a,b)\) when the limit exists and equals \(f(a,b)\).
Polynomials are continuous everywhere, and a rational function is continuous
wherever its denominator is nonzero. A function defined piecewise, with a
formula off one point and an assigned value at that point, is continuous there
exactly when the limit matches the assigned value.

## Partial derivatives

\(f_x\) differentiates with respect to \(x\) while treating \(y\) as a constant.
Geometrically it is the slope of the surface in the \(x\)-direction, that is,
the slope of the curve cut by the plane \(y=\) constant.

Clairaut's theorem says the mixed partials \(f_{xy}\) and \(f_{yx}\) are equal
wherever both are continuous, so the order of differentiation stops mattering.

The existence of both partial derivatives does NOT imply continuity in several
variables, which is the sharpest break from the one-variable theory.
Differentiability is the stronger condition: it requires the tangent plane to
be a genuine local approximation, and it does imply continuity.

## The chain rule and the gradient

With \(z=f(x,y)\), \(x=x(t)\), \(y=y(t)\):
\(dz/dt = f_x\,dx/dt + f_y\,dy/dt\). A tree diagram of dependencies gives one
term per path.

The gradient \(\nabla f = \langle f_x, f_y\rangle\) points in the direction of
steepest increase, and \(\|\nabla f\|\) is that greatest rate. The directional
derivative in a unit direction \(\vec u\) is \(D_{\vec u}f = \nabla f\cdot\vec u\),
which requires \(\vec u\) to be normalized first.

The gradient is orthogonal to level curves and level surfaces, which is what
makes \(\nabla F\) a normal vector for the tangent plane to \(F(x,y,z)=k\).

## Optimization

Critical points occur where \(\nabla f = \vec 0\) or a partial fails to exist.
The second-derivative test uses \(D = f_{xx}f_{yy} - (f_{xy})^2\): \(D>0\) with
\(f_{xx}>0\) gives a local minimum, \(D>0\) with \(f_{xx}<0\) a local maximum,
\(D<0\) a saddle point, and \(D=0\) is inconclusive.

Lagrange multipliers optimize \(f\) subject to \(g=k\) by solving
\(\nabla f = \lambda\nabla g\) together with the constraint. The geometric
content is that at an extremum the level curve of \(f\) is tangent to the
constraint curve, so their gradients are parallel.
""",
    ),
    (
        "Multiple Integrals",
        r"""
## Double integrals

\(\iint_R f\,dA\) sums \(f\) over a planar region, giving the signed volume under
the surface. Over a rectangle with continuous \(f\), Fubini's theorem allows
either order of integration.

Over a general region the limits carry the geometry. For a type I region the
inner limits are functions of \(x\) and the outer limits are constants; for type
II the roles swap. The outer limits must always be constants, because the final
result is a number.

Changing the order of integration requires redrawing the region and re-deriving
the limits from it. Swapping the differentials while keeping the old limits is
the standard error, and it is often the whole point of the exercise, because
one order can be elementary while the other is not.

## Polar coordinates

With \(x=r\cos\theta\), \(y=r\sin\theta\), the area element is
\(dA = r\,dr\,d\theta\). The factor \(r\) is not optional: it is the Jacobian,
and it accounts for the fact that a polar rectangle grows wider as \(r\)
increases. Circular regions and integrands containing \(x^2+y^2\) are the signal
to switch.

## Triple integrals

\(\iiint_E f\,dV\) extends the same idea to a solid. With \(f=1\) the integral
returns the volume of \(E\).

In cylindrical coordinates \(dV = r\,dz\,dr\,d\theta\), which suits solids with
an axis of symmetry. In spherical coordinates
\(dV = \rho^2\sin\phi\,d\rho\,d\phi\,d\theta\), which suits spheres and cones;
here \(\phi\) is measured from the positive \(z\)-axis and runs from \(0\) to
\(\pi\), while \(\theta\) runs from \(0\) to \(2\pi\).

Forgetting \(\rho^2\sin\phi\) is the spherical analogue of forgetting the \(r\),
and it produces an answer with the wrong units of volume.

## Applications and change of variables

Mass is \(\iiint \rho\,dV\) for a density \(\rho\); moments and centers of mass
follow by weighting each coordinate. The average value of \(f\) over a region is
its integral divided by the region's area or volume.

A general substitution \(x=g(u,v)\), \(y=h(u,v)\) requires the Jacobian factor
\(|\partial(x,y)/\partial(u,v)|\). The absolute value matters, because area must
come out positive regardless of how the transformation orients the region.
""",
    ),
    (
        "Vector Calculus",
        r"""
## Vector fields

A vector field \(\vec F(x,y,z)\) attaches a vector to each point. Gradient fields
\(\vec F = \nabla f\) are called conservative, and \(f\) is the potential
function.

## Line integrals

The line integral of a scalar function, \(\int_C f\,ds\), sums \(f\) along a
curve and is independent of the direction of travel. The line integral of a
vector field, \(\int_C \vec F\cdot d\vec r\), measures work and does reverse sign
when the orientation reverses.

## The fundamental theorem for line integrals

If \(\vec F=\nabla f\), then \(\int_C \vec F\cdot d\vec r = f(B)-f(A)\): the
integral depends only on the endpoints, so the field is path-independent and any
closed loop integrates to zero.

In a simply connected region, \(\vec F = \langle P,Q\rangle\) is conservative
exactly when \(\partial P/\partial y = \partial Q/\partial x\). The simple
connectivity hypothesis is not decorative; the standard vortex field satisfies
the partial-derivative test yet has nonzero circulation around the puncture at
the origin.

## Green's theorem

\(\oint_C (P\,dx + Q\,dy) = \iint_D (\partial Q/\partial x - \partial P/\partial y)\,dA\)
converts a line integral around a simple closed curve into a double integral
over the region it encloses, provided \(C\) is positively oriented,
counterclockwise, so the region stays on the left.

## Curl and divergence

\(\operatorname{curl}\vec F = \nabla\times\vec F\) measures local rotation and
returns a vector; \(\operatorname{div}\vec F = \nabla\cdot\vec F\) measures local
expansion and returns a scalar. A conservative field has zero curl, and the
divergence of any curl is zero.

## Surface integrals and the big theorems

A surface integral \(\iint_S \vec F\cdot d\vec S\) measures flux across a
surface, and its sign depends on the chosen orientation.

Stokes' theorem equates the circulation of \(\vec F\) around a closed boundary
curve with the flux of \(\operatorname{curl}\vec F\) through any surface that
curve bounds. The divergence theorem equates the flux of \(\vec F\) out of a
closed surface with the integral of \(\operatorname{div}\vec F\) over the solid
inside.

All three of Green's, Stokes', and the divergence theorem are the same
statement at different dimensions: the integral of a derivative over a region
equals the integral of the original quantity over that region's boundary.
""",
    ),
]


def post(title: str, content: str) -> dict:
    body = json.dumps({"title": title, "content": content, "campaign": COURSE}).encode()
    request = urllib.request.Request(API, data=body, headers={"content-type": "application/json"})
    with urllib.request.urlopen(request, timeout=120) as response:
        return json.loads(response.read().decode())


def main() -> int:
    imported = 0
    for index, (title, body) in enumerate(UNITS, 1):
        full_title = f"MA 26100 · {index}. {title}"
        content = HEADER + f"## Unit {index} — {title}\n" + body.strip() + "\n"
        try:
            result = post(full_title, content)
        except urllib.error.HTTPError as error:
            print(f"  FAIL {full_title}: {error.code} {error.read().decode(errors='replace')[:200]}")
            continue
        except Exception as error:  # noqa: BLE001
            print(f"  FAIL {full_title}: {error}")
            continue
        print(f"  imported material {result['material_id']}: {full_title}")
        imported += 1

    print(f"\n{imported}/{len(UNITS)} units imported.")
    return 0 if imported == len(UNITS) else 1


if __name__ == "__main__":
    sys.exit(main())
