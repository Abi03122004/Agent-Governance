import matplotlib.pyplot as plt
import matplotlib.patches as patches

fig, ax = plt.subplots(figsize=(14, 9.5), dpi=300)
ax.set_xlim(0, 1150)
ax.set_ylim(0, 800)
ax.axis('off')

# Colors matching the original image
HEADER_COLOR = '#20335e'
BORDER_COLOR = '#20335e'
BG_COLOR = '#ffffff'
PK_FK_COLOR = '#b93822'
FIELD_COLOR = '#222222'
LINE_COLOR = '#20335e'

def draw_table(ax, x, y, w, h, title, pk_fks, fields):
    # Overall table box
    rect = patches.FancyBboxPatch((x, y - h), w, h,
                                  boxstyle="round,pad=0,rounding_size=4",
                                  facecolor=BG_COLOR, edgecolor=BORDER_COLOR, linewidth=1.5)
    ax.add_patch(rect)
    
    # Header box (top 28 px)
    header_h = 28
    header_rect = patches.FancyBboxPatch((x, y - header_h), w, header_h,
                                         boxstyle="round,pad=0,rounding_size=4",
                                         facecolor=HEADER_COLOR, edgecolor=BORDER_COLOR, linewidth=1.5)
    ax.add_patch(header_rect)
    
    # Square bottom of header
    ax.add_patch(patches.Rectangle((x, y - header_h), w, 8, facecolor=HEADER_COLOR, edgecolor=HEADER_COLOR, linewidth=0))
    
    # Title text
    ax.text(x + 10, y - 18, title, color='#ffffff', fontsize=11, fontweight='bold', va='center')
    
    # PK / FK lines
    curr_y = y - header_h - 14
    for item in pk_fks:
        ax.text(x + 10, curr_y, item, color=PK_FK_COLOR, fontsize=9.5, fontweight='500', va='center')
        curr_y -= 16
        
    # Divider line
    ax.plot([x, x + w], [curr_y + 6, curr_y + 6], color='#e2e8f0', linewidth=1)
    curr_y -= 8
    
    # Normal fields
    for field in fields:
        ax.text(x + 10, curr_y, field, color=FIELD_COLOR, fontsize=9.5, va='center')
        curr_y -= 16

# 1. organizations (Top-Left)
draw_table(ax, 35, 730, 195, 150, "organizations", 
           ["id (PK)"], 
           ["name", "status", "created_at", "updated_at"])

# 2. projects (Top-Right)
draw_table(ax, 885, 750, 205, 115, "projects", 
           ["id (PK)", "organization_id (FK)"], 
           ["name", "environment / status", "created_at"])

# 3. agents (Top-Center)
draw_table(ax, 465, 730, 195, 185, "agents", 
           ["id (PK)", "organization_id (FK)", "project_id (FK)"], 
           ["name / owner", "environment", "purpose", "status (active/suspended)"])

# 4. policies (Middle-Right)
draw_table(ax, 885, 520, 205, 160, "policies", 
           ["id (PK)", "organization_id (FK)"], 
           ["name", "version / is_active", "rules_count", "created_at"])

# 5. runtime_actions (Center)
draw_table(ax, 465, 390, 195, 165, "runtime_actions", 
           ["id (PK)", "organization_id (FK)", "agent_id (FK)"], 
           ["tool / operation", "action_digest (SHA-256)", "decision / reason_code"])

# 6. audit_events (Bottom-Left)
draw_table(ax, 35, 320, 195, 170, "audit_events", 
           ["event_id (PK)", "organization_id (FK)", "agent_id (FK)"], 
           ["tool_name / event_type", "canonical_action_hash", "policy_decision", "event_hash / timestamp"])

# 7. approval_requests (Bottom-Center)
draw_table(ax, 465, 150, 195, 105, "approval_requests", 
           ["ticket_id (PK)", "organization_id, action_id (FK)"], 
           ["canonical_action_hash", "status / reason / approver"])

# 8. policy_rules (Lower Middle-Right)
draw_table(ax, 885, 290, 205, 115, "policy_rules", 
           ["id (PK)", "policy_id (FK)"], 
           ["decision / target_tool", "condition_expr", "priority / is_active"])

# 9. execution_authorizations (Bottom-Right)
draw_table(ax, 885, 125, 205, 95, "execution_authorizations", 
           ["id (PK)", "action_id (FK)"], 
           ["token_hash / expires_at", "used_at / created_at"])

# Lines & Cardinalities
# organizations -> projects (1 : N projects)
ax.plot([132, 132, 987, 987], [730, 775, 775, 750], color=LINE_COLOR, linewidth=1.5)
ax.text(560, 782, "1 : N projects", color='#111111', fontsize=9.5, fontweight='bold', ha='center',
        bbox=dict(boxstyle='square,pad=0.2', facecolor='white', edgecolor='none'))

# organizations -> agents (1 : N owns)
ax.plot([230, 465], [655, 655], color=LINE_COLOR, linewidth=1.5)
ax.text(347, 662, "1 : N owns", color='#111111', fontsize=9.5, fontweight='bold', ha='center',
        bbox=dict(boxstyle='square,pad=0.2', facecolor='white', edgecolor='none'))

# organizations -> runtime_actions (1 : N)
ax.plot([230, 345, 345, 465], [600, 600, 320, 320], color=LINE_COLOR, linewidth=1.5)
ax.text(355, 450, "1 : N", color='#111111', fontsize=9.5, fontweight='bold')

# organizations -> audit_events (1 : N)
ax.plot([132, 132], [580, 320], color=LINE_COLOR, linewidth=1.5)
ax.text(142, 450, "1 : N", color='#111111', fontsize=9.5, fontweight='bold')

# agents -> policies (1 : 1)
ax.plot([660, 775, 775, 885], [635, 635, 440, 440], color=LINE_COLOR, linewidth=1.5)
ax.text(785, 530, "1 : 1", color='#111111', fontsize=9.5, fontweight='bold')

# agents -> runtime_actions (1 : N)
ax.plot([562, 562], [545, 390], color=LINE_COLOR, linewidth=1.5)
ax.text(572, 465, "1 : N", color='#111111', fontsize=9.5, fontweight='bold')

# agents -> approval_requests (1 : N)
ax.plot([660, 715, 715, 660], [580, 580, 95, 95], color=LINE_COLOR, linewidth=1.5)
ax.text(725, 340, "1 : N", color='#111111', fontsize=9.5, fontweight='bold')

# policies -> policy_rules (1 : N)
ax.plot([987, 987], [360, 290], color=LINE_COLOR, linewidth=1.5)
ax.text(997, 325, "1 : N", color='#111111', fontsize=9.5, fontweight='bold')

# policy_rules -> execution_authorizations (1 : N)
ax.plot([987, 987], [175, 125], color=LINE_COLOR, linewidth=1.5)
ax.text(997, 150, "1 : N", color='#111111', fontsize=9.5, fontweight='bold')

plt.tight_layout()
out_path = r"d:\Projects\Agent Governance\docs\er_diagram.png"
plt.savefig(out_path, bbox_inches='tight', dpi=300)
print("Saved to", out_path)

