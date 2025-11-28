using Sandbox;

[Title( "Rail Switch" )]
[Category( "Rail System" )]
[Icon( "alt_route" )]
public sealed class RailSwitch : Component, Component.ITriggerListener
{
	[Property] public RailCart TargetCart { get; set; }

	// Два варианта пути
	[Property, Group( "Routes" )] public string RouteA { get; set; } = "Path02";
	[Property, Group( "Routes" )] public string RouteB { get; set; } = "Path02_01";

	[Property, Group( "Settings" )] public bool TriggerOnUse { get; set; } = true;
	[Property, Group( "Settings" )] public bool TriggerOnEnter { get; set; } = false;

	// Внутреннее состояние рычага (false = A, true = B)
	private bool _toggleState = false;

	protected override void OnUpdate()
	{
		if ( TriggerOnUse && Input.Pressed( "use" ) )
		{
			CheckUse();
		}
	}

	private void CheckUse()
	{
		var camera = Scene.Camera;
		if ( camera == null ) return;

		// Ищем игрока для игнора луча
		GameObject playerObject = null;
		var playerBody = camera.Components.GetInAncestorsOrSelf<Rigidbody>();
		if ( playerBody != null ) playerObject = playerBody.GameObject;
		else playerObject = camera.GameObject.Root;

		var tr = Scene.Trace.Ray( camera.WorldPosition, camera.WorldPosition + camera.WorldRotation.Forward * 200 )
			.IgnoreGameObjectHierarchy( camera.GameObject )
			.IgnoreGameObjectHierarchy( playerObject )
			.WithoutTags( "player", "trigger" )
			.Run();

		if ( tr.Hit )
		{
			if ( tr.GameObject == GameObject || tr.GameObject.IsDescendant( GameObject ) )
			{
				ToggleSwitch();
			}
		}
	}

	public void OnTriggerEnter( Collider other )
	{
		if ( !TriggerOnEnter ) return;
		if ( other.Tags.Has( "player" ) ) ToggleSwitch();
	}

	public void OnTriggerExit( Collider other ) { }

	private void ToggleSwitch()
	{
		if ( TargetCart == null )
		{
			Log.Error( "[RailSwitch] Error: Target Cart is missing!" );
			return;
		}

		// 1. Переключаем внутреннее состояние рычага
		_toggleState = !_toggleState;

		// 2. Выбираем маршрут на основе состояния рычага
		// Если _toggleState == false -> берем A
		// Если _toggleState == true  -> берем B
		string nextRoute = _toggleState ? RouteB : RouteA;

		// Для красоты логов: узнаем, что сейчас запланировано у вагонетки
		string currentPending = TargetCart.ActiveOrPendingRoute;

		Log.Info( $"[RailSwitch] Lever flipped! State: {(_toggleState ? "B" : "A")}" );
		Log.Info( $"[RailSwitch] Changing Cart plan: '{currentPending}' -> '{nextRoute}'" );

		// 3. Отправляем команду
		TargetCart.SwitchRoute( nextRoute );
	}
}
