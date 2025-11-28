using Sandbox;
using Sandbox.Citizen;
using System.Linq;
using System.Collections.Generic;
using System;

[Title( "Rail Cart" )]
[Category( "Rail System" )]
[Icon( "tram" )]
public sealed class RailCart : Component
{
	// =========================================================
	// SETTINGS
	// =========================================================

	[Property, Group( "Rail Settings" )] public GameObject PathNetworkObject { get; set; }
	[Property, Group( "Rail Settings" )] public string RouteName { get; set; } = "Main_Line";
	[Property, Group( "Rail Settings" )] public float MoveSpeed { get; set; } = 100.0f;

	[Property, Group( "Rail Settings" )] public float TurnSpeed { get; set; } = 5.0f;

	[Property, Group( "Rail Settings" ), Title( "Model Rotation Offset" )]
	public Angles RotationOffset { get; set; } = Angles.Zero;

	[Property, Group( "Rail Settings" )] public float LookAheadAmount { get; set; } = 0.05f;

	// --- AUDIO SETTINGS ---
	[Property, Group( "Audio Settings" )] public SoundEvent MoveSound { get; set; }
	[Property, Group( "Audio Settings" )] public float MaxVolume { get; set; } = 1.0f;
	[Property, Group( "Audio Settings" )] public float VolumeFadeSpeed { get; set; } = 3.0f; // Скорость затухания/появления
	[Property, Group( "Audio Settings" )] public float PitchMin { get; set; } = 0.8f;
	[Property, Group( "Audio Settings" )] public float PitchMax { get; set; } = 1.2f;

	private PathNetwork Network;

	[Property, Group( "Seat Position" )] public Vector3 SitOffset { get; set; } = new Vector3( 0, 0, 10 );
	[Property, Group( "Seat Position" )] public Vector3 ExitOffset { get; set; } = new Vector3( 50, 0, 0 );
	[Property, Group( "Seat Animation" ), Range( -50, 50 )] public float SitAnimHeight { get; set; } = 10.0f;
	[Property, Group( "Seat Camera" )] public float PitchClamp { get; set; } = 80.0f;
	[Property, Group( "Seat Camera" )] public float ThirdPersonDistance { get; set; } = 150.0f;

	// =========================================================
	// STATE
	// =========================================================
	private PathRoute _currentRoute;
	private int _currentSegmentIndex = 0;
	private float _segmentT = 0.0f;

	private string _nextRequestedRoute = "";
	private string _previousRouteName = "";

	public string ActiveOrPendingRoute => string.IsNullOrEmpty( _nextRequestedRoute ) ? RouteName : _nextRequestedRoute;

	private GameObject _currentUser;
	private Angles _currentLookAngles;
	private bool _isThirdPerson = true;

	// Audio State
	private SoundHandle _soundHandle;
	private float _currentVolume = 0.0f;
	private float _currentInputForSound = 0.0f; // Для сглаживания инпута

	private bool IsActive => _currentUser.IsValid();

	protected override void OnStart()
	{
		InitializeRoute();
	}

	protected override void OnUpdate()
	{
		HandleSeatInput();

		if ( IsActive )
		{
			HandleMovement();
			UpdateCamera();
			UpdateSittingAnimation();
		}

		// Обновляем звук всегда (даже если игрок вышел, звук должен плавно затухнуть)
		UpdateSound();
	}

	protected override void OnDestroy()
	{
		// Обязательно останавливаем звук при уничтожении объекта
		_soundHandle?.Stop();
		_soundHandle = null;
		base.OnDestroy();
	}

	// =========================================================
	// API
	// =========================================================

	public void SwitchRoute( string newRouteName )
	{
		_nextRequestedRoute = newRouteName;
		Log.Info( $"[RailCart] Next junction set to: '{_nextRequestedRoute}'" );
	}

	// =========================================================
	// MOVEMENT LOGIC
	// =========================================================

	private void InitializeRoute()
	{
		if ( PathNetworkObject != null )
			Network = PathNetworkObject.Components.Get<PathNetwork>();

		if ( Network == null )
			Network = Scene.GetAllComponents<PathNetwork>().FirstOrDefault();

		if ( Network == null ) return;

		_currentRoute = Network.GetRoute( RouteName );

		if ( _currentRoute == null || _currentRoute.Points.Count < 2 ) return;

		_currentSegmentIndex = 0;
		_segmentT = 0.0f;
		_nextRequestedRoute = "";
		_previousRouteName = "";

		SnapToTrack( true );
	}

	private void HandleMovement()
	{
		if ( _currentRoute == null || _currentRoute.Points.Count < 2 ) return;

		float inputDir = Input.AnalogMove.x;

		// Сохраняем input для звука
		_currentInputForSound = inputDir;

		if ( inputDir == 0 ) return;

		var pA = _currentRoute.Points[_currentSegmentIndex];
		if ( _currentSegmentIndex + 1 >= _currentRoute.Points.Count ) return;
		var pB = _currentRoute.Points[_currentSegmentIndex + 1];

		if ( !pA.IsValid() || !pB.IsValid() ) return;

		float segmentLength = pA.WorldPosition.Distance( pB.WorldPosition );
		if ( segmentLength <= 0.001f ) segmentLength = 1.0f;

		float deltaT = (MoveSpeed * Time.Delta) / segmentLength;

		_segmentT += deltaT * inputDir;

		if ( _segmentT > 1.0f )
		{
			if ( _currentSegmentIndex < _currentRoute.Points.Count - 2 )
			{
				_segmentT -= 1.0f;
				_currentSegmentIndex++;
			}
			else
			{
				if ( TryConnectToNextRoute( true ) ) { }
				else { _segmentT = 1.0f; }
			}
		}
		else if ( _segmentT < 0.0f )
		{
			if ( _currentSegmentIndex > 0 )
			{
				_segmentT += 1.0f;
				_currentSegmentIndex--;
			}
			else
			{
				if ( TryConnectToNextRoute( false ) ) { }
				else { _segmentT = 0.0f; }
			}
		}

		SnapToTrack( false );
	}

	private bool TryConnectToNextRoute( bool movingForward )
	{
		var junctionPoint = movingForward ? _currentRoute.Points.Last() : _currentRoute.Points.First();
		if ( !junctionPoint.IsValid() ) return false;

		var candidates = new List<PathRoute>();

		foreach ( var route in Network.Routes )
		{
			if ( route == _currentRoute ) continue;
			if ( route.Points.Count < 2 ) continue;

			if ( movingForward )
			{
				if ( route.Points.First().WorldPosition.Distance( junctionPoint.WorldPosition ) < 5.0f )
					candidates.Add( route );
			}
			else
			{
				if ( route.Points.Last().WorldPosition.Distance( junctionPoint.WorldPosition ) < 5.0f )
					candidates.Add( route );
			}
		}

		if ( candidates.Count == 0 ) return false;

		PathRoute chosenRoute = null;

		if ( !string.IsNullOrEmpty( _nextRequestedRoute ) )
		{
			chosenRoute = candidates.FirstOrDefault( r => r.Name == _nextRequestedRoute );
		}

		if ( chosenRoute == null && !string.IsNullOrEmpty( _previousRouteName ) )
		{
			chosenRoute = candidates.FirstOrDefault( r => r.Name == _previousRouteName );
		}

		if ( chosenRoute == null ) chosenRoute = candidates.First();

		Log.Info( $"[RailCart] Switching track to: '{chosenRoute.Name}'" );

		_previousRouteName = RouteName;
		RouteName = chosenRoute.Name;
		_currentRoute = chosenRoute;
		_nextRequestedRoute = "";

		if ( movingForward )
		{
			_currentSegmentIndex = 0;
			_segmentT = 0.0f;
		}
		else
		{
			_currentSegmentIndex = _currentRoute.Points.Count - 2;
			_segmentT = 1.0f;
		}

		return true;
	}

	private void SnapToTrack( bool instantRotation = false )
	{
		if ( _currentRoute == null ) return;
		if ( _currentSegmentIndex >= _currentRoute.Points.Count - 1 ) return;

		Vector3 currentPos = PathNetwork.GetPointOnPath( _currentRoute, _currentSegmentIndex, _segmentT );
		WorldPosition = currentPos;

		Vector3 lookAheadPos = GetLookAheadPosition( LookAheadAmount );
		Vector3 direction = (lookAheadPos - currentPos).Normal;

		if ( direction.LengthSquared < 0.0001f )
		{
			Vector3 lookBackPos = GetLookAheadPosition( -LookAheadAmount );
			direction = (currentPos - lookBackPos).Normal;
		}

		if ( direction != Vector3.Zero )
		{
			var trackRotation = Rotation.LookAt( direction, Vector3.Up );
			var targetRotation = trackRotation * RotationOffset.ToRotation();

			if ( instantRotation )
			{
				WorldRotation = targetRotation;
			}
			else
			{
				WorldRotation = Rotation.Slerp( WorldRotation, targetRotation, Time.Delta * TurnSpeed );
			}
		}
	}

	private Vector3 GetLookAheadPosition( float tOffset )
	{
		int targetIndex = _currentSegmentIndex;
		float targetT = _segmentT + tOffset;

		while ( targetT > 1.0f )
		{
			if ( targetIndex < _currentRoute.Points.Count - 2 )
			{
				targetT -= 1.0f;
				targetIndex++;
			}
			else
			{
				targetT = 1.0f;
				break;
			}
		}

		while ( targetT < 0.0f )
		{
			if ( targetIndex > 0 )
			{
				targetT += 1.0f;
				targetIndex--;
			}
			else
			{
				targetT = 0.0f;
				break;
			}
		}

		return PathNetwork.GetPointOnPath( _currentRoute, targetIndex, targetT );
	}

	// =========================================================
	// AUDIO LOGIC
	// =========================================================

	private void UpdateSound()
	{
		if ( MoveSound == null ) return;

		// 1. Determine Target Volume
		// Если игрок сидит И нажимает кнопку движения (input != 0), целевая громкость Max.
		// Иначе целевая громкость 0.
		float targetVol = 0.0f;

		if ( IsActive && MathF.Abs( Input.AnalogMove.x ) > 0.1f )
		{
			targetVol = MaxVolume;
		}

		// 2. Smoothly Interpolate Volume
		_currentVolume = MathX.Lerp( _currentVolume, targetVol, Time.Delta * VolumeFadeSpeed );

		// 3. Manage Sound Handle
		if ( _currentVolume > 0.01f )
		{
			if ( _soundHandle == null )
			{
				// Старт звука
				_soundHandle = Sound.Play( MoveSound, WorldPosition );
			}

			if ( _soundHandle != null )
			{
				// Обновляем позицию звука (чтобы он ехал вместе с вагонеткой)
				_soundHandle.Position = WorldPosition;
				_soundHandle.Volume = _currentVolume;

				// Питч зависит от целевой громкости (имитация разгона)
				// Чем громче (быстрее), тем выше питч
				float pitchAlpha = _currentVolume / MaxVolume;
				_soundHandle.Pitch = MathX.Lerp( PitchMin, PitchMax, pitchAlpha );
			}
		}
		else
		{
			// Если громкость упала почти до 0, останавливаем хэндл, чтобы не тратить ресурсы
			if ( _soundHandle != null )
			{
				_soundHandle.Stop();
				_soundHandle = null;
			}
		}
	}

	// =========================================================
	// SEAT LOGIC
	// =========================================================

	private void HandleSeatInput()
	{
		if ( Input.Pressed( "use" ) )
		{
			if ( IsActive ) StandUp();
			else TrySit();
		}

		if ( IsActive && Input.Pressed( "l" ) )
		{
			_isThirdPerson = !_isThirdPerson;
		}
	}

	private void TrySit()
	{
		var camera = Scene.Camera;
		if ( camera == null ) return;

		var playerBody = camera.Components.GetInAncestorsOrSelf<Rigidbody>();
		if ( playerBody == null ) return;

		var playerObject = playerBody.GameObject;

		var tr = Scene.Trace.Ray( camera.WorldPosition, camera.WorldPosition + camera.WorldRotation.Forward * 200 )
			.IgnoreGameObjectHierarchy( camera.GameObject )
			.IgnoreGameObjectHierarchy( playerObject )
			.WithoutTags( "player", "trigger" )
			.Run();

		if ( tr.Hit && tr.GameObject == GameObject )
		{
			SitDown( playerObject );
		}
	}

	private void SitDown( GameObject player )
	{
		Log.Info( "RailCart: Player mounting..." );
		_currentUser = player;

		if ( Scene.Camera != null )
			_currentLookAngles = Scene.Camera.WorldRotation.Angles();

		var rb = player.Components.Get<Rigidbody>( FindMode.EverythingInSelf );
		if ( rb != null ) rb.Enabled = false;

		var controller = player.Components.GetAll<Component>( FindMode.EverythingInSelf )
			.FirstOrDefault( c => c.GetType().Name == "PlayerController" || c.GetType().Name == "CharacterController" );
		if ( controller != null ) controller.Enabled = false;

		player.SetParent( GameObject );
		player.LocalPosition = SitOffset;
		player.LocalRotation = Rotation.Identity;

		Log.Info( "RailCart: Player mounted." );
	}

	private void StandUp()
	{
		if ( !_currentUser.IsValid() ) return;

		var player = _currentUser;
		Log.Info( "RailCart: Player dismounting..." );

		player.SetParent( null );

		var exitPos = WorldPosition + (WorldRotation * ExitOffset) + Vector3.Up * 10.0f;
		player.WorldPosition = exitPos;
		player.WorldRotation = Rotation.FromYaw( _currentLookAngles.yaw );

		if ( Scene.Camera != null )
		{
			if ( Scene.Camera.GameObject.Parent != player )
				Scene.Camera.GameObject.SetParent( player );
			Scene.Camera.LocalPosition = new Vector3( 0, 0, 64 );
			Scene.Camera.LocalRotation = Rotation.Identity;
		}

		var controller = player.Components.GetAll<Component>( FindMode.EverythingInSelf )
			.FirstOrDefault( c => c.GetType().Name == "PlayerController" || c.GetType().Name == "CharacterController" );
		if ( controller != null ) controller.Enabled = true;

		var rb = player.Components.Get<Rigidbody>( FindMode.EverythingInSelf );
		if ( rb != null )
		{
			rb.Enabled = true;
			rb.Velocity = Vector3.Zero;
		}

		_currentUser = null;
		Log.Info( "RailCart: Player dismounted." );
	}

	private void UpdateSittingAnimation()
	{
		var animator = _currentUser.Components.GetInDescendantsOrSelf<CitizenAnimationHelper>();
		var renderer = _currentUser.Components.GetInDescendantsOrSelf<SkinnedModelRenderer>();

		if ( animator != null )
		{
			animator.IsSitting = true;
			animator.Sitting = CitizenAnimationHelper.SittingStyle.Chair;
			animator.WithVelocity( Vector3.Zero );
			animator.WithWishVelocity( Vector3.Zero );

			if ( Scene.Camera != null )
				animator.WithLook( Scene.Camera.WorldRotation.Forward );
		}

		if ( renderer != null )
		{
			renderer.Set( "sit", 1 );
			renderer.Set( "sit_offset_height", SitAnimHeight );
		}
	}

	private void UpdateCamera()
	{
		if ( Scene.Camera == null ) return;

		var lookInput = Input.AnalogLook;
		_currentLookAngles.pitch += lookInput.pitch;
		_currentLookAngles.yaw += lookInput.yaw;
		_currentLookAngles.pitch = _currentLookAngles.pitch.Clamp( -PitchClamp, PitchClamp );

		var rotation = _currentLookAngles.ToRotation();
		Scene.Camera.WorldRotation = rotation;

		var eyePosition = _currentUser.WorldPosition + Vector3.Up * 64.0f;

		if ( _isThirdPerson )
		{
			var camForward = rotation.Forward;
			var camPos = eyePosition - (camForward * ThirdPersonDistance);

			var tr = Scene.Trace.Ray( eyePosition, camPos )
				.IgnoreGameObjectHierarchy( _currentUser )
				.IgnoreGameObjectHierarchy( GameObject )
				.Radius( 5.0f )
				.Run();

			Scene.Camera.WorldPosition = tr.EndPosition;
		}
		else
		{
			Scene.Camera.WorldPosition = eyePosition;
		}
	}
}
