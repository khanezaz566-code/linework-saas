import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from linework.trace import ink_map, find_fused_discs
from linework.split import estimate_width
from tests.diag_join_problems import make, ALL
verdict = {"draw_chip_qfp":"same","draw_pcb_schematic":"BETTER","draw_bicycle_frame":"WORSE","draw_scissors_shears":"BETTER","draw_audio_equalizer":"same","draw_telescope_tripod":"BETTER","draw_lightbulb_threads":"same","draw_isometric_cube":"same","draw_celtic_knot":"same","draw_pen_nib_sparkle":"BETTER","draw_dome_corner_junction":"WORSE","draw_bga_microcontroller":"BETTER","draw_biometric_fingerprint":"same","draw_space_station_iss":"BETTER","draw_bonsai_tree":"same","draw_steam_locomotive":"BETTER","draw_filigree_skeleton_key":"BETTER","draw_heraldic_coat_of_arms":"same","draw_geodesic_dome":"same"}
for i, d in enumerate(ALL):
    if d.__name__ not in verdict: continue
    img, _ = make(i)
    D = ink_map(img); w = estimate_width(D)
    find_fused_discs.debug.clear()
    f = find_fused_discs(D, w)
    print(f"{verdict[d.__name__]:6} {d.__name__:<28} " + " | ".join(f"R/rs={e['r_ratio']:.2f} arc={e['arc_bins']}/36 votes={e['votes']:.0f}" for e in find_fused_discs.debug))
