using Sandbox;
using System.Collections.Generic;
using System.Linq;

[Title( "Path Network" )]
[Category( "Rail System" )]
[Icon( "map" )]
public sealed class PathNetwork : Component
{
	[Property] public List<PathRoute> Routes { get; set; } = new();

	// Default to true, but properly checked in OnUpdate
	[Property] public bool ShowDebugLines { get; set; } = true;

	protected override void OnStart()
	{
		Log.Info( $"PathNetwork: Initialized with {Routes.Count} routes." );
	}

	protected override void OnUpdate()
	{
		// Strict check: If disabled, do absolutely nothing
		if ( !ShowDebugLines ) return;

		DrawRouteGizmos();
	}

	public PathRoute GetRoute( string routeName )
	{
		return Routes.FirstOrDefault( r => r.Name == routeName );
	}

	// =========================================================
	// GIZMOS DRAWING
	// =========================================================
	private void DrawRouteGizmos()
	{
		if ( Routes == null ) return;

		foreach ( var route in Routes )
		{
			if ( route.Points == null || route.Points.Count < 2 ) continue;

			// Set color for this route's lines and text
			Gizmo.Draw.Color = route.RouteColor;

			// 1. Draw Lines
			if ( route.Mode == PathInterpolationMode.Linear )
			{
				for ( int i = 0; i < route.Points.Count - 1; i++ )
				{
					var p1 = route.Points[i];
					var p2 = route.Points[i + 1];

					// Check for validity of the point components/objects
					if ( IsPointValid( p1 ) && IsPointValid( p2 ) )
					{
						Gizmo.Draw.Line( p1.WorldPosition, p2.WorldPosition );
						DrawDirectionArrow( p1.WorldPosition, p2.WorldPosition );
					}
				}
			}
			else // Catmull-Rom
			{
				int stepsPerSegment = 15;

				for ( int i = 0; i < route.Points.Count - 1; i++ )
				{
					if ( !IsPointValid( route.Points[i] ) || !IsPointValid( route.Points[i + 1] ) ) continue;

					Vector3 lastPos = GetPointOnPath( route, i, 0.0f );

					for ( int step = 1; step <= stepsPerSegment; step++ )
					{
						float t = step / (float)stepsPerSegment;
						Vector3 nextPos = GetPointOnPath( route, i, t );

						Gizmo.Draw.Line( lastPos, nextPos );
						lastPos = nextPos;
					}

					// Draw direction arrow in the middle of the segment
					Vector3 midPos = GetPointOnPath( route, i, 0.5f );
					Vector3 midTan = GetTangentOnPath( route, i, 0.5f );
					Gizmo.Draw.Arrow( midPos - midTan * 5, midPos + midTan * 5 );
				}
			}

			// 2. Draw Route Name
			if ( route.Points.Count > 0 && IsPointValid( route.Points[0] ) )
			{
				Gizmo.Draw.Text( $"Route: {route.Name} ({route.Mode})", new Transform( route.Points[0].WorldPosition + Vector3.Up * 32 ) );
			}
		}
	}

	private void DrawDirectionArrow( Vector3 start, Vector3 end )
	{
		var midPoint = (start + end) * 0.5f;
		var direction = (end - start).Normal;
		Gizmo.Draw.Arrow( midPoint - direction * 10, midPoint + direction * 10 );
	}

	// Helper to safely check validity without accessing .IsValid() on null
	private static bool IsPointValid( PathPoint point )
	{
		// Assuming PathPoint is a Component or GameObject wrapper
		return point != null && point.IsValid();
	}

	// =========================================================
	// MATH HELPERS (Static)
	// =========================================================

	private static Vector3 GetPointExtended( List<PathPoint> points, int index )
	{
		int count = points.Count;
		if ( count == 0 ) return Vector3.Zero;

		if ( index >= 0 && index < count )
		{
			if ( IsPointValid( points[index] ) )
				return points[index].WorldPosition;
			return Vector3.Zero;
		}

		// Extrapolate Start
		if ( index < 0 )
		{
			var p0 = IsPointValid( points[0] ) ? points[0].WorldPosition : Vector3.Zero;
			var p1 = IsPointValid( points[1] ) ? points[1].WorldPosition : p0;
			return p0 - (p1 - p0);
		}

		// Extrapolate End
		if ( index >= count )
		{
			var pLast = IsPointValid( points[count - 1] ) ? points[count - 1].WorldPosition : Vector3.Zero;
			var pPrev = IsPointValid( points[count - 2] ) ? points[count - 2].WorldPosition : pLast;
			return pLast + (pLast - pPrev);
		}

		return Vector3.Zero;
	}

	public static Vector3 GetPointOnPath( PathRoute route, int i, float t )
	{
		if ( route.Mode == PathInterpolationMode.Linear )
		{
			var p0 = route.Points[i].WorldPosition;
			var p1 = route.Points[i + 1].WorldPosition;
			return Vector3.Lerp( p0, p1, t );
		}
		else
		{
			var p0 = GetPointExtended( route.Points, i - 1 );
			var p1 = GetPointExtended( route.Points, i );
			var p2 = GetPointExtended( route.Points, i + 1 );
			var p3 = GetPointExtended( route.Points, i + 2 );

			return CalculateCatmullRom( p0, p1, p2, p3, t );
		}
	}

	public static Vector3 GetTangentOnPath( PathRoute route, int i, float t )
	{
		if ( route.Mode == PathInterpolationMode.Linear )
		{
			var p0 = route.Points[i].WorldPosition;
			var p1 = route.Points[i + 1].WorldPosition;
			return (p1 - p0).Normal;
		}
		else
		{
			var p0 = GetPointExtended( route.Points, i - 1 );
			var p1 = GetPointExtended( route.Points, i );
			var p2 = GetPointExtended( route.Points, i + 1 );
			var p3 = GetPointExtended( route.Points, i + 2 );

			return CalculateCatmullRomDerivative( p0, p1, p2, p3, t ).Normal;
		}
	}

	private static Vector3 CalculateCatmullRom( Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t )
	{
		float t2 = t * t;
		float t3 = t2 * t;

		return 0.5f * (
			(2.0f * p1) +
			(-p0 + p2) * t +
			(2.0f * p0 - 5.0f * p1 + 4.0f * p2 - p3) * t2 +
			(-p0 + 3.0f * p1 - 3.0f * p2 + p3) * t3
		);
	}

	private static Vector3 CalculateCatmullRomDerivative( Vector3 p0, Vector3 p1, Vector3 p2, Vector3 p3, float t )
	{
		float t2 = t * t;

		return 0.5f * (
			(-p0 + p2) +
			(4.0f * p0 - 10.0f * p1 + 8.0f * p2 - 2.0f * p3) * t +
			(-3.0f * p0 + 9.0f * p1 - 9.0f * p2 + 3.0f * p3) * t2 * 1.5f
		);
	}
}
