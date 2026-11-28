"""Plot recorded evaluator geometry and measurements in project units."""

from dataclasses import dataclass, field
from html import escape

from shapely.geometry import Polygon

from fpg_lab.visualization import figures

PASS, FAIL, WARN, NEUTRAL = "#69db9c", "#ff7796", "#ffcd73", "#c0c9d8"


@dataclass
class Layer:
    label: str
    points: list
    color: str
    overlay: str
    dash: str = "solid"
    fill: bool = False
    markers: bool = False


@dataclass
class Observation:
    label: str
    measurements: dict
    color: str
    layers: list[Layer] = field(default_factory=list)
    room_ids: tuple = ()


def label(value):
    return value.replace("_", " ")


def number(value):
    return "—" if value is None else f"{value:.4g}"


def length(value):
    return f"{number(value)} u"


def area(value):
    return f"{number(value)} u²"


def _geo(shape, name, color, overlay):
    if not shape:
        return []
    kind = shape["type"]
    if kind == "GeometryCollection":
        return [layer for part in shape["geometries"] for layer in _geo(part, name, color, overlay)]
    coords = shape["coordinates"]
    if kind.startswith("Multi"):
        return [
            layer
            for part in coords
            for layer in _geo(
                {"type": kind[5:], "coordinates": part},
                name,
                color,
                overlay,
            )
        ]
    if kind == "Polygon":
        return [Layer(name, ring, color, overlay, fill=len(coords) == 1) for ring in coords]
    if kind in {"LineString", "LinearRing"}:
        return [Layer(name, coords, color, overlay)]
    return []


def _midpoint(line):
    return tuple((a + b) / 2 for a, b in zip(line[0], line[-1], strict=True))


def _direction_layers(entrances, direction, depth):
    layers = []
    for entrance in entrances:
        start = _midpoint(entrance)
        tip = tuple(a + d * depth * 0.45 for a, d in zip(start, direction, strict=True))
        layers.extend(
            [
                Layer("Entrance", entrance, WARN, "Entrances", dash="dash"),
                Layer("Inward direction", [start, tip], WARN, "Directions"),
            ]
        )
    return layers


def observations(key, evaluation, plan):
    payload = evaluation.get("visualization_payload") or {}
    names = {room["id"].strip(): f"{room['name']} ({room['id']})" for room in plan["rooms"]}
    if key == "geometry_integrity":
        geometries = payload.get("findings", [])
        return [
            Observation(
                finding["message"],
                {
                    "Finding": label(finding["code"]).capitalize(),
                    **{label(m["name"]): area(m["value"]) for m in finding["metrics"]},
                },
                FAIL,
                [
                    layer
                    for shape in geometries[index]
                    for layer in _geo(shape, label(finding["code"]).capitalize(), FAIL, "Findings")
                ]
                if index < len(geometries)
                else [],
                tuple(finding["subject_ids"]),
            )
            for index, finding in enumerate(evaluation["findings"])
        ]
    if key == "enclosed_voids":
        return [
            Observation(
                f"Void {i} · {area(void['area'])}",
                {
                    "Area": area(void["area"]),
                    "Area tolerance": area(payload["area_tolerance"]),
                    "Scoring": "Violation" if void["affects_score"] else "Within tolerance",
                },
                FAIL if void["affects_score"] else WARN,
                [
                    Layer(
                        "Scoring void" if void["affects_score"] else "Tolerated void",
                        void["points"],
                        FAIL if void["affects_score"] else WARN,
                        "Void polygons",
                        fill=True,
                    ),
                ],
            )
            for i, void in enumerate(payload.get("voids", []), start=1)
        ]
    if key == "inward_recess":
        return _recesses(payload, names)
    if key == "room_size_consistency":
        result = []
        for measured, row in zip(payload.get("rules", []), size_matrix(payload), strict=True):
            rule = measured["rule"]
            details = {key: value for key, value in row.items() if key != "Rule"}
            if measured["kind"] == "relation":
                details.update(
                    {
                        "Feasible ratio": _bounds(
                            measured["feasible_min"], measured["feasible_max"]
                        ),
                        "Reference area": f"{area(measured['reference_area'])} ({rule['reference_aggregation']})",
                        "Compared area": f"{area(measured['compared_area'])} ({rule['compared_aggregation']})",
                    }
                )
            else:
                details.update(
                    {
                        "Feasible minimum spread": number(measured["feasible_min"]),
                        "Smallest room": area(measured["smallest_area"]),
                        "Largest room": area(measured["largest_area"]),
                    }
                )
            details.update(
                {
                    "Violation delta": number(measured["violation_delta"]),
                    "Full penalty delta": number(measured["full_penalty_delta"]),
                }
            )
            result.append(
                Observation(
                    row["Rule"],
                    details,
                    PASS if measured["violation_delta"] == 0 else FAIL,
                    room_ids=tuple(measured["room_ids"]),
                )
            )
        return result
    if key == "room_relationship_quality":
        result = []
        for measured in payload.get("rules", []):
            rule = measured["rule"]
            score = measured["score"]
            details = {
                "Rule type": measured["kind"].capitalize(),
                "Rule score": number(score),
                "Preferred maximum": length(rule["preferred_maximum_distance"]),
                "Zero-score distance": length(rule["zero_score_distance"]),
                "Weight": number(rule["weight"]),
            }
            if measured["kind"] == "proximity":
                room_ids = []
                for pair in measured["pairs"]:
                    source, target = pair["source_id"], pair["target_id"]
                    details[names.get(source, source)] = (
                        f"Nearest target {names.get(target, target)} · "
                        f"{length(pair['distance'])} · score {number(pair['score'])}"
                    )
                    room_ids.extend((source, target))
            else:
                room_ids = measured["room_ids"]
                details["Participants"] = ", ".join(
                    names.get(room_id, room_id) for room_id in room_ids
                )
                details["Farthest pair"] = " ↔ ".join(
                    names.get(room_id, room_id) for room_id in measured["pair"]
                )
                details["Maximum centroid distance"] = length(measured["distance"])
            result.append(
                Observation(
                    f"{rule['rule_id']} · {number(score)}",
                    details,
                    PASS if score == 100 else WARN,
                    room_ids=tuple(dict.fromkeys(room_ids)),
                )
            )
        return result
    return []


def _recesses(payload, names):
    result = []
    for i, recess in enumerate(payload.get("recesses", []), start=1):
        for j, section in enumerate((recess["region"], *recess["sections"]), start=-1):
            is_region = j == -1
            name = f"Recess {i}" if is_region else f"Recess {i} · section {j + 1}"
            codes = section["violation_codes"]
            nested_violation = is_region and any(
                item["violation_codes"] for item in recess["sections"]
            )
            color = FAIL if codes or nested_violation else PASS
            entrances = [recess["entrance"]] if is_region else section.get("entrances", [])
            measurements = {
                "Status": ", ".join(
                    label(code.removeprefix("INWARD_RECESS_")).lower() for code in codes
                )
                or ("Contains violating sections" if nested_violation else "Accepted"),
                "Width": length(section["width"]),
                "Depth": length(section["depth"]),
                "Area": area(section["area"]),
                "Depth / width": number(section["depth_to_width_ratio"]),
                "Nesting level": section["level"],
                "Branches": recess["branch_count"],
                "Parent sections": ", ".join(str(index + 1) for index in section["parent_indices"])
                or "—",
                "Inward direction": str(tuple(section["direction"])),
            }
            overlay = "Recess regions" if is_region else "Sections"
            layers = [
                Layer(
                    name,
                    ring,
                    color,
                    overlay,
                    "dot" if not is_region else "solid",
                    fill=is_region and len(polygon) == 1,
                )
                for polygon in section["polygons"]
                for ring in polygon
            ]
            layers.extend(_direction_layers(entrances, section["direction"], section["depth"]))
            for parent in section["parent_indices"]:
                parent_entrances = recess["sections"][parent].get("entrances", [])
                if entrances and parent_entrances:
                    layers.append(
                        Layer(
                            f"Section {parent + 1} → {j + 1}",
                            [_midpoint(parent_entrances[0]), _midpoint(entrances[0])],
                            NEUTRAL,
                            "Branch links",
                            "dashdot",
                        )
                    )
            for boundary in section["room_boundaries"]:
                room = names.get(boundary["room_id"], boundary["room_id"])
                measurements[f"Boundary · {room}"] = length(boundary["shared_length"])
                layers.extend(
                    Layer(room, line, NEUTRAL, "Room boundaries", "dash")
                    for line in boundary["segments"]
                )
            result.append(Observation(name, measurements, color, layers))
    return result


def size_matrix(payload):
    rows = []
    for measured in payload.get("rules", []):
        rule = measured["rule"]
        if measured["kind"] == "relation":
            name = f"{label(rule['compared_type'])} / {label(rule['reference_type'])}"
            configured = _bounds(rule["min_ratio"], rule["max_ratio"])
            effective = _bounds(measured["effective_min"], measured["effective_max"])
        else:
            name = f"{label(rule['room_type'])} size spread"
            configured = f"≤ {number(rule['maximum_spread_ratio'])}"
            effective = f"≤ {number(measured['effective_max'])}"
        rows.append(
            {
                "Rule": name,
                "Configured": configured,
                "Actual": number(measured["actual"]),
                "Effective": effective,
                "Score": number(measured["score"]),
                "Penalty": number(measured["penalty"]),
                "Weight": number(rule["weight"]),
                "Status": "Satisfied" if measured["violation_delta"] == 0 else "Outside preference",
            }
        )
    return rows


def _bounds(minimum, maximum):
    if minimum is None:
        return f"≤ {number(maximum)}"
    if maximum is None:
        return f"≥ {number(minimum)}"
    return f"{number(minimum)} to {number(maximum)}"


def inspection_plot(plan, title, units, items, evaluation, selected, enabled):
    result = figures.floor_plan({**plan, "openings": []}, title=title)
    rooms = plan["rooms"]
    selected_rooms = items[selected].room_ids if selected is not None else ()
    for trace in result.data:
        trace.update(
            line_color=NEUTRAL, opacity=0.48, showlegend=False, fillcolor="rgba(148,163,184,.13)"
        )
    for trace, room in zip(result.data[1:], rooms, strict=True):
        if room["id"].strip() in selected_rooms:
            trace.update(line_color=items[selected].color, line_width=3, opacity=0.9)
    payload = evaluation.get("visualization_payload") or {}
    result.layout.annotations = ()
    areas = {measured["room_id"]: measured["area"] for measured in payload.get("rooms", [])}
    for room in rooms:
        # Label positions are presentation geometry. Areas come from the evaluator.
        point = Polygon(
            [(p["x"], p["y"]) for p in room["boundary"]["points"]]
        ).representative_point()
        name = escape(room["name"])
        room_id = room["id"].strip()
        if room_id in areas:
            name += f"<br>{area(areas[room_id])}"
        result.add_annotation(x=point.x, y=point.y, text=name, showarrow=False)
    legend = set()
    order = [i for i in range(len(items)) if i != selected]
    if selected is not None:
        order.append(selected)
    for i in order:
        item = items[i]
        measurements = "".join(
            f"<br>{escape(key)} · {escape(str(value))}"
            for key, value in list(item.measurements.items())[:4]
        )
        for layer in item.layers:
            if layer.overlay not in enabled or not layer.points:
                continue
            focused = selected is None or selected == i
            x, y = zip(*layer.points, strict=True)
            group = (layer.overlay, layer.color)
            result.add_scatter(
                x=x,
                y=y,
                mode="lines+markers" if layer.markers else "lines",
                line={"width": 4 if focused else 2, "color": layer.color, "dash": layer.dash},
                marker={"size": 8, "color": layer.color},
                fill="toself" if layer.fill else None,
                opacity=0.95 if focused else 0.22,
                name=layer.label,
                legendgroup=f"{layer.overlay}-{layer.color}",
                showlegend=group not in legend,
                hoveron="fills+points" if layer.fill else "points",
                hovertext=f"{escape(item.label)}<br>{escape(layer.label)}{measurements}",
                hoverinfo="text",
            )
            legend.add(group)
            if layer.overlay == "Directions":
                result.add_annotation(
                    x=x[-1],
                    y=y[-1],
                    ax=x[0],
                    ay=y[0],
                    axref="x",
                    ayref="y",
                    xref="x",
                    yref="y",
                    showarrow=True,
                    text="",
                    arrowhead=3,
                    arrowcolor=layer.color,
                    opacity=0.95 if focused else 0.22,
                )
    result.update_layout(title=None, uirevision=title, margin={"t": 12, "b": 48}, dragmode="pan")
    result.update_xaxes(title=f"X · project units ({units} u/m)")
    return result
