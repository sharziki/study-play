#!/usr/bin/env python3
"""Import CS 18000 course material into Intellect.

Why this exists: CS 18000 had an exam nine days out and **zero** questions,
because no material had ever been imported for it. The only thing filed under
the course was `examples/newton.md`, a bundled physics demo.

Sourcing note, and the honest limitation. Unlike STAT 350, CS 18000 publishes
no public course website for the current term: `cs.purdue.edu/homes/cs180` is
a Spring 2011 frameset, and the current material lives behind Brightspace,
which needs the student's own session. So the topic scope here comes from the
**official Purdue catalog description**, retrieved from Self-Service:

    https://selfservice.mypurdue.purdue.edu/prod/bwckctlg.p_display_courses
    ?term_in=202710&one_subj=CS&sel_crse_strt=18000&sel_crse_end=18000

That description enumerates the syllabus topics verbatim, and those topic
names are what this file is built around. The explanatory text under each
heading is standard Java semantics, written here so every generated question
has an exact source quote to cite, which is the app's grounding requirement.

**This is scaffolding, not a substitute for the real lecture notes.** When
Brightspace material is exported, import it the normal way and it will sit
alongside this. Treat a conflict between the two as the lecture notes winning.
"""

import json
import sys
import urllib.error
import urllib.request

API = "http://127.0.0.1:4173/api/materials"
COURSE = "CS 18000"

CATALOG = (
    "Problem solving and algorithms, implementation of algorithms in a high "
    "level programming language, conditionals, the iterative approach and "
    "debugging, collections of data, searching and sorting, solving problems "
    "by decomposition, the object-oriented approach, subclasses of existing "
    "classes, handling exceptions that occur when the program is running, "
    "graphical user interfaces (GUIs), data stored in files, abstract data "
    "types, a glimpse at topics from other CS courses."
)

HEADER = f"""# CS 18000 — Problem Solving and Object-Oriented Programming

Scope from the official Purdue catalog description:

> {CATALOG}

"""

UNITS: list[tuple[str, str]] = [
    (
        "Java Fundamentals — Types, Variables, and Control Flow",
        """
## Primitive types and reference types

Java has eight primitive types: byte, short, int, long, float, double, char,
and boolean. A primitive variable holds its value directly. Every other type
is a reference type, and a reference variable holds the address of an object
rather than the object itself. This distinction explains most beginner
surprises in Java.

Assigning a primitive copies the value, so changing the copy leaves the
original untouched. Assigning a reference copies the address, so two variables
then refer to the same object and a change made through one is visible through
the other.

int overflows silently. Integer.MAX_VALUE + 1 is Integer.MIN_VALUE, not an
error, because two's-complement arithmetic wraps around. Anything that can
exceed roughly two billion needs long.

Integer division truncates toward zero: 7 / 2 is 3, not 3.5. Writing 7.0 / 2
forces floating-point division because one operand is a double. The modulus
operator % gives the remainder, and for negative operands its result takes the
sign of the left operand: -7 % 3 is -1.

Floating point cannot represent most decimal fractions exactly. 0.1 + 0.2 does
not equal 0.3 in double arithmetic. Comparing doubles with == is therefore a
bug; compare the absolute difference against a small tolerance instead.

## Casting

Widening conversions (int to long, int to double) happen implicitly because no
information is lost. Narrowing conversions require an explicit cast and can
lose information: (int) 3.99 is 3, because a cast to an integer type truncates
rather than rounds.

## Conditionals

An if statement chooses between paths based on a boolean expression. Java has
no implicit truthiness: the condition must actually be a boolean, so `if (x)`
where x is an int does not compile.

The && and || operators short-circuit. In `a && b`, b is only evaluated when a
is true, which is what makes `if (s != null && s.length() > 0)` safe. The
non-short-circuiting & and | always evaluate both sides.

A switch statement compares one value against several cases. Without a break,
execution falls through into the next case, which is occasionally intended and
usually a bug.

## Loops

A while loop tests before the body runs, so its body may execute zero times. A
do-while loop tests after, so its body always runs at least once. A for loop
packages initialization, condition, and update on one line and is the natural
choice when the iteration count is known.

An off-by-one error comes from the boundary: `for (int i = 0; i <= n; i++)`
runs n+1 times, which overruns an array of length n. The enhanced for loop,
`for (int value : array)`, avoids index arithmetic entirely but gives no index
and cannot modify the array's elements through the loop variable.

break exits the enclosing loop immediately. continue skips the rest of the
current iteration and proceeds to the next one.
""",
    ),
    (
        "Arrays, Strings, and Collections of Data",
        """
## Arrays

An array is a fixed-size, homogeneous, zero-indexed container. Its length is
fixed at creation and exposed as the field `.length`, with no parentheses.
Accessing index -1 or index length throws ArrayIndexOutOfBoundsException at
run time rather than at compile time.

An array of a reference type is created filled with null, not with objects. So
`String[] names = new String[3];` holds three nulls, and calling a method on
any of them throws NullPointerException until each slot is assigned.

A two-dimensional array in Java is an array of arrays. Rows may therefore have
different lengths, which is called a jagged array, and `grid[i].length` is the
length of row i specifically.

Arrays are objects, so passing one to a method passes a reference. The method
can modify the caller's array elements. It cannot replace the caller's array,
because the reference itself was passed by value.

## Strings

A String is immutable. Every operation that appears to change a string
actually returns a new one, so `s.toUpperCase()` has no effect unless its
result is assigned. Building a string in a loop with += creates a new object
each iteration; StringBuilder exists for that case.

== on strings compares references, not characters. Two strings with identical
characters can live at different addresses and compare false. `.equals()`
compares contents and is what string comparison means in practice. String
literals are interned into a shared pool, which is why == sometimes appears to
work and is exactly what makes the bug hard to find.

## ArrayList

ArrayList grows on demand, which is its advantage over an array. It stores
objects only, so an ArrayList<Integer> autoboxes each int into an Integer.
Its size is `.size()`, a method, in contrast to an array's `.length` field and
a String's `.length()` method.

Removing from an ArrayList while iterating forward with an index skips
elements, because every remaining element shifts down one position. Iterating
backward, or using an Iterator's own remove, avoids this.
""",
    ),
    (
        "Methods, Decomposition, and Recursion",
        """
## Decomposition

Solving a problem by decomposition means splitting it into smaller methods
that each do one nameable thing. A method with a clear name and a single
responsibility can be tested and reasoned about alone, which is what makes a
large program tractable.

## Parameter passing

Java is strictly pass-by-value. For a primitive, the value is copied and the
method cannot affect the caller's variable. For an object, the reference is
copied, so the method can mutate the object the reference points at but cannot
make the caller's variable point somewhere else.

## Overloading

Two methods may share a name when their parameter lists differ in type, count,
or order. The compiler picks which one to call from the argument types, so
overload resolution happens at compile time. Return type alone cannot
distinguish two overloads.

## Scope and lifetime

A local variable exists only inside the block that declares it and must be
assigned before it is read. An instance field belongs to one object and is
default-initialized: 0 for numerics, false for boolean, null for references.
A static field belongs to the class itself, so every instance shares one copy.

## Recursion

A recursive method calls itself on a smaller input. It needs a base case that
returns without recursing, and a recursive case that makes measurable progress
toward that base case. Missing either one produces infinite recursion, which
ends in StackOverflowError because every pending call occupies a stack frame.

Recursion and iteration are equally powerful. Recursion is preferable when the
problem itself is recursive, such as traversing a tree or dividing a range in
half, and iteration is preferable when a simple counter suffices.
""",
    ),
    (
        "Searching and Sorting",
        """
## Linear search

Linear search examines each element in turn until it finds the target or
exhausts the collection. It works on unsorted data and takes O(n) comparisons
in the worst case.

## Binary search

Binary search requires the data to be sorted. It compares the target with the
middle element and discards half the remaining range each step, giving
O(log n) comparisons. Running it on unsorted data does not report an error; it
returns a wrong answer, which is worse.

The midpoint computed as (low + high) / 2 can overflow for very large indices.
low + (high - low) / 2 computes the same midpoint without overflowing.

## Selection sort and insertion sort

Selection sort repeatedly finds the smallest remaining element and swaps it
into place. It always performs about n^2/2 comparisons, regardless of the
input, and makes at most n swaps.

Insertion sort builds a sorted prefix by inserting each next element into its
correct position. It is O(n^2) in the worst case but O(n) on data that is
already nearly sorted, which makes it the faster choice on small or nearly
ordered inputs.

## Merge sort

Merge sort divides the array in half, sorts each half recursively, and merges
the two sorted halves. It is O(n log n) in every case, including the worst,
and it is stable, meaning equal elements keep their original relative order.
The cost is O(n) extra space for the merge.

## Why the order of growth matters

Constant factors matter at small n, but the order of growth decides what is
feasible at large n. Going from O(n^2) to O(n log n) is the difference between
an hour and a second on a large input, and no amount of micro-optimization
closes that gap.
""",
    ),
    (
        "The Object-Oriented Approach — Classes, Objects, and Encapsulation",
        """
## Classes and objects

A class is a blueprint; an object is an instance created from it with new.
Each object has its own copy of the instance fields, while static members
belong to the class and are shared.

## Constructors

A constructor has the class's name and no return type. It runs when an object
is created and puts the object into a valid initial state. If no constructor
is written, Java supplies a no-argument default. Writing any constructor
removes that default, so adding a parameterized constructor can break existing
`new Thing()` calls.

The keyword this refers to the current object. It disambiguates a field from a
parameter of the same name, as in `this.name = name`, and `this(...)` calls
another constructor of the same class.

## Encapsulation

Encapsulation means keeping fields private and exposing behavior through
methods. It matters because the class can then enforce its own invariants: a
private balance with a deposit method can reject a negative amount, whereas a
public field can be set to anything by anyone.

A getter that returns a reference to a mutable field leaks the internals,
because the caller can then modify the object's state directly, which defeats
the encapsulation the private field was providing.

## toString, equals, and hashCode

Every class inherits from Object. The inherited toString prints a class name
and a hash code, so a readable class overrides it. The inherited equals
compares references, so a class whose objects are compared by value must
override equals, and must override hashCode consistently with it, or the
object will misbehave in hash-based collections.

## static

A static method belongs to the class and cannot access instance fields,
because there is no instance. This is why main, which is static, cannot touch
instance state without first creating an object.
""",
    ),
    (
        "Inheritance, Polymorphism, and Abstract Data Types",
        """
## Subclasses

A subclass extends an existing class, inheriting its accessible members and
adding or changing behavior. Java has single inheritance: a class extends at
most one superclass, though it may implement several interfaces.

A subclass constructor implicitly calls the superclass's no-argument
constructor first. When the superclass has no such constructor, the subclass
must call `super(...)` explicitly as its first statement.

## Overriding versus overloading

Overriding replaces an inherited method with one of the same name and the same
parameter list in a subclass. Overloading adds a method with the same name and
a different parameter list. The @Override annotation makes the compiler check
that a method really does override something, which catches a misspelled name
or a wrong parameter list that would otherwise silently become an overload.

## Polymorphism

A superclass reference may point at a subclass object. Which overridden method
runs is decided at run time by the object's actual type, not by the reference's
declared type; this is dynamic dispatch. Field access, by contrast, is resolved
at compile time from the declared type.

The declared type determines what can be called. A Shape reference cannot call
a Circle-only method without a cast, and an incorrect cast throws
ClassCastException at run time.

## Abstract classes and interfaces

An abstract class cannot be instantiated and may declare abstract methods that
subclasses must implement. An interface declares a contract of method
signatures; a class implements it and supplies the bodies. Use an abstract
class when subclasses share state and implementation, and an interface when
unrelated classes need to promise the same capability.

## Abstract data types

An abstract data type is defined by its operations and their behavior, not by
its representation. A List is an ADT: it promises ordered access by position,
while ArrayList and LinkedList implement that promise differently. Programming
against the ADT rather than the implementation is what allows one to be
swapped for the other.
""",
    ),
    (
        "Exceptions and Debugging",
        """
## What an exception is

An exception is an object representing a problem that occurred while the
program was running. Throwing one unwinds the call stack until some enclosing
try block catches it; if none does, the program terminates and prints a stack
trace.

## Checked and unchecked

A checked exception, such as IOException, must be either caught or declared in
the method's throws clause, and the compiler enforces this. An unchecked
exception extends RuntimeException — NullPointerException,
ArrayIndexOutOfBoundsException, ArithmeticException — and needs no
declaration, because these indicate programming errors that should be fixed
rather than routinely caught.

## try, catch, finally

Catch blocks are tested in order, so a catch of a subclass must precede a catch
of its superclass; the reverse order does not compile, because the broader
catch makes the narrower one unreachable.

A finally block runs whether or not an exception was thrown, and even when the
try block returns. It is where resources get released. try-with-resources
closes anything implementing AutoCloseable automatically and is preferable.

Catching Exception and doing nothing is the worst possible handler: it hides
the failure and leaves the program running with corrupt state.

## Reading a stack trace

A stack trace lists the call chain with the innermost frame first. The first
line of the trace names the exception type and its message; the topmost frame
in your own code is where to look first. The "Caused by" section, when present,
names the original failure that was wrapped.

## Debugging

A debugger with a breakpoint shows actual variable values at a chosen line,
which beats guessing from print statements. The systematic approach is to
reduce the input until the failure is minimal, form one hypothesis about the
cause, and test that hypothesis, rather than changing code at random until the
symptom disappears.
""",
    ),
    (
        "File I/O and Graphical User Interfaces",
        """
## Reading and writing files

File input and output can fail for reasons the program cannot control: the
file may be missing, unreadable, or locked. This is why the file APIs throw
checked exceptions, forcing the programmer to acknowledge the failure path.

Scanner reads formatted input conveniently: hasNextLine checks whether more
input remains, and nextLine consumes and returns it. Mixing nextInt with
nextLine is a classic trap, because nextInt leaves the line terminator in the
buffer and the following nextLine returns an empty string.

A stream must be closed, or the program leaks a file handle and buffered
output may never reach the disk. try-with-resources closes it even when an
exception occurs, which a plain try block does not.

Writing without append mode truncates the existing file, discarding its
contents.

## Graphical user interfaces

A GUI is event-driven. Rather than the program dictating the order of
operations, the user does: the program registers listeners and waits, and the
toolkit invokes a listener when the corresponding event occurs. This inverts
the flow of control compared with a console program.

Swing components are arranged by a layout manager rather than by absolute
coordinates, so the interface adapts when the window is resized. BorderLayout
places components in five regions, FlowLayout runs them left to right, and
GridLayout tiles them in equal cells.

Swing is not thread-safe. Components must be created and updated on the event
dispatch thread, and long work must not run on it, or the interface freezes
because the thread that repaints the window is busy.
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
        full_title = f"CS 18000 · {index}. {title}"
        content = HEADER + f"## Unit {index} — {title}\n" + body.strip() + "\n"
        try:
            result = post(full_title, content)
        except urllib.error.HTTPError as error:
            detail = error.read().decode(errors="replace")[:200]
            print(f"  FAIL {full_title}: {error.code} {detail}")
            continue
        except Exception as error:  # noqa: BLE001
            print(f"  FAIL {full_title}: {error}")
            continue
        print(f"  imported material {result['material_id']}: {full_title}")
        imported += 1

    print(f"\n{imported}/{len(UNITS)} units imported.")
    print("Generate questions with:  python3 -c \"import study; study.generate(None, 8)\"")
    return 0 if imported == len(UNITS) else 1


if __name__ == "__main__":
    sys.exit(main())
