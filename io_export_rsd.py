"""
This script exports PlayStation SDK compatible RSD,PLY,MAT files from Blender.
Supports normals, colors and texture mapped triangles.
Only one mesh can be exported at a time.
"""

import os
import bpy

from bpy.props import (CollectionProperty,
                       StringProperty,
                       BoolProperty,
                       EnumProperty,
                       FloatProperty,
                       )

from bpy_extras.io_utils import (ImportHelper,
                                 ExportHelper,
                                 axis_conversion,
                                 )

bl_info = {
    "name":         "Export: Playstation RSD,PLY,MAT Model Format",
    "author":       "Jobert 'Lameguy' Villamor (Lameguy64), ABelliqueux",
    "blender":      (2,80,0),
    "version":      (3,0,1),
    "location":     "File > Export",
    "description":  "Export mesh to PlayStation SDK compatible RSD,PLY,MAT format",
    "support":      "COMMUNITY",
    "category":     "Import-Export"
}

class ExportRSD(bpy.types.Operator, ExportHelper):
    
    bl_idname       = "export_mesh.rsd"
    bl_label        = "Export RSD,PLY,MAT"
    
    filename_ext    = ".rsd"
    filter_glob: StringProperty(default="*.rsd;*.ply;*.mat", options={'HIDDEN'})
    
    # Export options
    exp_applyModifiers: BoolProperty(
        name="Apply Modifiers",
        description="Apply modifiers to the exported mesh.",
        default=True,
        )
        
    exp_coloredTexPolys: BoolProperty(
        name="Colored Textured Polygons",
        description="Export all textured faces as vertex colored, "
                    "light source calculation on such faces will be "
                    "disabled however due to libgs limitations.",
        default=False,
        )
    
    exp_scaleFactor: FloatProperty(
        name="Scale Factor",
        description="Scale factor of exported mesh.",
        min=0.01, max=1000.0,
        default=1.0,
        )
        
    def execute(self, context):
        
        # Trivia: bpy.path.ensure_ext got borked in newer versions of Blender due to a 'fix' introduced in
        # Thu Sep 3 13:09:16 2015 +0200 so I had to use this messy trick to get extensions to work properly
        #
        # Said 'bugfix' addresses the issue in bpy.path.ensure_ext with extensions with double periods (such as .tar.gz)
        # but it also breaks its intended function of adding or replacing an existing file extension with the specified
        # extension. This 'bugfix' still persists in 2.76b and no one but I (lameguy64) seems to notice this problem
        # probably because I'm the only one making export plugins that output more than one file in different extensions
        # so I doubt this will ever get fixed.
        
        filepath = self.filepath
        filepath = filepath.rstrip(self.filename_ext) # Quick fix to get around the aforementioned 'bugfix'
        rsd_filepath = bpy.path.ensure_ext(filepath, self.filename_ext)
        ply_filepath = bpy.path.ensure_ext(filepath, '.ply')
        mat_filepath = bpy.path.ensure_ext(filepath, '.mat')
        
        # Get object context
        obj = context.object
        
        # Get mesh
        if self.exp_applyModifiers:
            depsgraph = context.evaluated_depsgraph_get()
            mesh = obj.evaluated_get(depsgraph).to_mesh()
        else:
            mesh = obj.to_mesh()
        
        if not mesh.loop_triangles and mesh.polygons:
            mesh.calc_loop_triangles()
        
        # Write PLY file
        with open(ply_filepath, "w") as f:
            
            f.write("@PLY940102\n")
            f.write("%d %d %d\n" % (len(mesh.vertices), (len(mesh.vertices)+len(mesh.loop_triangles)), len(mesh.loop_triangles)))
            
            # Write vertices
            f.write("# Vertices\n")
            for v in mesh.vertices:
                f.write("%E %E %E\n" % (v.co.x * self.exp_scaleFactor, -v.co.z * self.exp_scaleFactor, v.co.y * self.exp_scaleFactor))

            # Write normals
            f.write("# Normals\n")
            f.write("# Smooth normals begin here\n")
            for v in mesh.vertices:
                f.write("%E %E %E\n" % (v.normal.x, -v.normal.z, v.normal.y))
                
            f.write("# Flat normals begin here\n")
            flatnorms_start = len(mesh.vertices)
            for p in mesh.loop_triangles:
                f.write("%E %E %E\n" % (p.normal.x, -p.normal.z, p.normal.y))

            # Write polygons
            f.write("# Polygon\n")
            for i,p in enumerate(mesh.loop_triangles):
                
                # Write vertex indices
                if len(p.vertices) == 3:
                    f.write("0 %d %d %d 0 " % (p.vertices[0], p.vertices[2], p.vertices[1]))
                elif len(p.vertices) == 4:
                    f.write("1 %d %d %d %d " % (p.vertices[3], p.vertices[2], p.vertices[0], p.vertices[1]))
                
                # Write normal indices and shading mode
                if p.use_smooth:
                    if len(p.vertices) == 3:
                        f.write("%d %d %d 0" % (p.vertices[0], p.vertices[2], p.vertices[1]))
                    elif len(p.vertices) == 4:
                        f.write("%d %d %d %d" % (p.vertices[3], p.vertices[2], p.vertices[0], p.vertices[1]))
                else:
                    n = flatnorms_start+i
                    if len(p.vertices) == 3:
                        f.write("%d %d %d 0" % (n, n, n))
                    elif len(p.vertices) == 4:
                        f.write("%d %d %d %d" % (n, n, n, n))
                    
                f.write("\n")
            
        # Write MAT file
        with open(mat_filepath, "w") as f:
        
            f.write("@MAT940801\n")
            f.write("%d\n" % len(mesh.loop_triangles))
            
            
            if mesh.vertex_colors:
                mesh_cols = mesh.vertex_colors.active.data
            else:
                mesh_cols = None
                
            for i,p in enumerate(mesh.loop_triangles):
                
                f.write("%d\t 0 " % i)
                
                # Set flat or gouraud
                if p.use_smooth:
                    f.write("G ")
                else:
                    f.write("F ")
                    
                # So that vertex colors will be correct for textured polys
                color_mul = 255.0
                pol_textured = False
                    
                # Check if polygon is flat or gouraud shaded
                if mesh_cols is not None:
                    col = [mesh_cols[loop_index].color[:] for loop_index in p.loops]
                    # Check if polygon is flat shaded
                    if (col[0] == col[1]) and (col[1] == col[2]) and (col[2] == col[0]):
                        # is flat...
                        pol_gouraud = False
                    else:
                        # is gouraud...
                        pol_gouraud = True
                else:
                    pol_gouraud = False
                    
                # Write texture coordinates
                if pol_textured:
                    if self.exp_coloredTexPolys:
                        if pol_gouraud:
                            f.write("H ")
                        else:
                            f.write("D ")
                    else:
                        f.write("T ")
                    f.write("%d " % (tex_table[i]-1))
                    uv = [mesh_uvs[loop_index].uv for loop_index in p.loops]
                    if len(p.vertices) == 3:
                        uv = (uv[0],
                              uv[2],
                              uv[1],
                              )
                    elif len(p.vertices) == 4:
                        uv = (uv[3],
                              uv[2],
                              uv[0],
                              uv[1]
                              )
                    tex_w = 1024
                    tex_h = 512
                    for j,c in enumerate(p.vertices):
                        f.write("%d %d " % (round(tex_w*uv[j].x), round(tex_h-(tex_h*uv[j].y))))
                    if len(p.vertices) == 3:
                        f.write("0 0 ")
                else:
                    if pol_gouraud:
                        f.write("G ")
                    else:
                        f.write("C ")
                        
                # Write vertex colors
                if mesh_cols is not None:
                    if self.exp_coloredTexPolys or not pol_textured:
                        if pol_gouraud:
                            if len(p.vertices) == 4:
                                index_tab = [ 3, 2, 0, 1 ]
                            else:
                                index_tab = [ 0, 2, 1 ]
                            for j,c in enumerate(p.vertices):
                                color = col[index_tab[j]]
                                color = (int(color[0]*color_mul), int(color[1]*color_mul), int(color[2]*color_mul))
                                f.write("%d %d %d " % (color[0], color[1], color[2]))
                            # according to filefrmt.pdf, section 2-10, figure 2-15, "(4th vertex is 0,0,0 for triangles)"
                            if len(p.vertices) == 3:
                                f.write("0 0 0")
                        else:
                            color = col[0]
                            color = (int(color[0]*color_mul),
                                     int(color[1]*color_mul),
                                     int(color[2]*color_mul),
                                     )
                            f.write("%d %d %d " % color[:])
                else:
                    f.write("%d %d %d " % (color_mul, color_mul, color_mul))
                    
                f.write("\n")
        
        # Write RSD file        
        with open(rsd_filepath, "w") as f:
            f.write("@RSD940102\n")
            f.write("PLY=%s\n" % bpy.path.basename(ply_filepath))
            f.write("MAT=%s\n" % bpy.path.basename(mat_filepath))
            f.write("NTEX=0\n")
            f.close()
            
        return {'FINISHED'}
    
    
# For registering to Blender menus
def menu_func(self, context):
    self.layout.operator(ExportRSD.bl_idname, text="PlayStation RSD (.rsd,.ply,.mat)")

def register():
    bpy.utils.register_class(ExportRSD)
    bpy.types.TOPBAR_MT_file_export.append(menu_func)
    
def unregister():
    bpy.types.TOPBAR_MT_file_export.remove(menu_func)
    bpy.utils.unregister_class(ExportRSD)

if __name__ == "__main__":
    register()
