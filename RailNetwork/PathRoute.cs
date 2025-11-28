using Sandbox;
using System.Collections.Generic;

public enum PathInterpolationMode
{
	Linear,
	CatmullRom
}

[Title( "Path Route" )]
public class PathRoute
{
	[Property] public string Name { get; set; } = "New Route";
	[Property] public Color RouteColor { get; set; } = Color.Green;

	// Режим сглаживания
	[Property] public PathInterpolationMode Mode { get; set; } = PathInterpolationMode.Linear;

	[Property] public List<PathPoint> Points { get; set; } = new();
}
