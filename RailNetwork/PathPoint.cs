using Sandbox;

[Title( "Path Point" )]
[Category( "Rail System" )]
[Icon( "place" )]
public sealed class PathPoint : Component
{
	// Color of the point in the editor
	[Property] public Color PointColor { get; set; } = Color.White;

	// Radius of the gizmo sphere
	[Property] public float GizmoRadius { get; set; } = 8.0f;

	protected override void OnUpdate()
	{
		// 1. Find the PathNetwork in the ancestors (parents)
		var network = Components.GetInAncestors<PathNetwork>();

		// 2. If the network exists and ShowDebugLines is false, do not draw anything
		if ( network != null && !network.ShowDebugLines )
			return;

		// 3. Draw Gizmos
		DrawGizmos();
	}

	private void DrawGizmos()
	{
		// Draw sphere (using WorldPosition)
		Gizmo.Draw.Color = PointColor;
		Gizmo.Draw.SolidSphere( WorldPosition, GizmoRadius );

		// Draw object name above the point (text always faces camera)
		Gizmo.Draw.Color = Color.White;
		Gizmo.Draw.Text( GameObject.Name, new Transform( WorldPosition + Vector3.Up * 16 ) );
	}
}
